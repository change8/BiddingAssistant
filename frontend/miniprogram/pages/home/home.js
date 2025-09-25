const { API_BASE } = require('../../utils/config')

const TAB_DEFS = [
  { id: 'hard_requirements', title: '废标项/硬性要求' },
  { id: 'scoring_items', title: '评分项' },
  { id: 'submission_format', title: '投标形式' },
  { id: 'technical_requirements', title: '技术要求' },
  { id: 'cost_items', title: '成本项' },
  { id: 'bid_timeline', title: '投标日历' }
]

const PRIORITY_LABELS = {
  critical: '极高优先级',
  high: '高优先级',
  medium: '中优先级',
  low: '关注即可'
}

function normaliseItem(raw = {}) {
  const priority = String(raw.priority || 'medium').toLowerCase()
  const level = ['critical', 'high', 'medium', 'low'].includes(priority) ? priority : 'medium'
  const startVal = Number(raw.source_start)
  const endVal = Number(raw.source_end)
  return {
    title: raw.title || raw.milestone || raw.event || '要点',
    why_important: raw.why_important || raw.reason || raw.summary || '',
    guidance: raw.guidance || raw.action || raw.recommendation || '',
    details: raw.details || raw.notes || raw.impact || '',
    milestone: raw.milestone || '',
    date: raw.date || raw.deadline || '',
    source_excerpt: raw.source_excerpt || '',
    source_start: Number.isFinite(startVal) ? startVal : null,
    source_end: Number.isFinite(endVal) ? endVal : null,
    priority: level,
    priorityLabel: PRIORITY_LABELS[level]
  }
}

function normaliseResult(result = {}) {
  const incoming = {}
  if (Array.isArray(result.tabs)) {
    result.tabs.forEach((tab) => {
      if (tab && tab.id) incoming[tab.id] = tab
    })
  }
  const tabs = TAB_DEFS.map((def) => {
    const source = incoming[def.id] || {}
    const items = Array.isArray(source.items) ? source.items.map(normaliseItem) : []
    return {
      id: def.id,
      title: source.title || def.title,
      items
    }
  })
  return {
    summary: result.summary || '',
    tabs
  }
}

function findDefaultTab(tabs = []) {
  const withItems = tabs.find((tab) => (tab.items || []).length)
  return (withItems || tabs[0] || {}).id || ''
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function highlightContext(context = '', excerpt = '') {
  if (!excerpt) {
    return escapeHtml(context)
  }
  let index = context.indexOf(excerpt)
  let match = excerpt
  if (index === -1) {
    const trimmed = excerpt.trim()
    if (trimmed) {
      index = context.indexOf(trimmed)
      match = trimmed
    }
  }
  if (index === -1) {
    return `${escapeHtml(context)}\n\n（未能精确定位摘录，已显示上下文）`
  }
  const before = escapeHtml(context.slice(0, index))
  const middle = escapeHtml(context.slice(index, index + match.length))
  const after = escapeHtml(context.slice(index + match.length))
  return `${before}<mark>${middle}</mark>${after}`
}

Page({
  data: {
    input: '',
    result: normaliseResult({}),
    jobId: null,
    status: '',
    loading: false,
    activeTabId: 'hard_requirements',
    currentItems: [],
    hasSource: false,
    snippetVisible: false,
    snippetTitle: '',
    snippetMeta: '',
    snippetContent: ''
  },
  onInput(e) {
    this.setData({ input: e.detail.value })
  },
  onFillDemo() {
    const demo = `本项目交付周期为合同签订后30日内完成，需提交阶段性里程碑成果。投标人须满足合格投标人资格条件，具备相应资质证书与近三年类似项目业绩不少于2个。

技术部分要求满足最低配置与必达参数，详见附件，但附件暂未提供。质保期不少于3年。验收环节需使用唯一验收工具完成专项测试。

付款方式：到货并初验合格支付50%，最终验收合格支付50%。质保金10%自最终验收后一年内无质量问题退还。

本项目仅限原厂授权唯一的品牌参与投标，不接受等效。`
    this.setData({ input: demo })
  },
  onAnalyze() {
    const text = (this.data.input || '').trim()
    if (!text) return wx.showToast({ title: '请先粘贴文本', icon: 'none' })

    this.setData({
      loading: true,
      status: '分析中...请稍候',
      result: normaliseResult({}),
      jobId: null,
      hasSource: false,
      activeTabId: 'hard_requirements',
      currentItems: []
    })

    wx.request({
      url: `${API_BASE}/analyze/text`,
      method: 'POST',
      header: { 'content-type': 'application/json' },
      data: { text },
      success: (res) => {
        const job = res.data || {}
        this._handleJob(job)
      },
      fail: (err) => {
        console.error('analyze/text error', err)
        wx.showToast({ title: '接口请求失败', icon: 'none' })
        this.setData({ loading: false, status: '接口请求失败' })
      }
    })
  },
  _handleJob(job) {
    const status = job.status || ''
    if (status === 'completed' && job.result) {
      const normalized = normaliseResult(job.result)
      const activeId = findDefaultTab(normalized.tabs)
      this.setData({
        loading: false,
        status: '分析完成',
        result: normalized,
        jobId: job.job_id || null,
        hasSource: !!job.has_source_text,
        activeTabId: activeId || 'hard_requirements'
      }, () => {
        this.updateCurrentItems()
      })
      return
    }

    if (status === 'failed') {
      wx.showToast({ title: job.error || '分析失败', icon: 'none' })
      this.setData({ loading: false, status: job.error || '分析失败', jobId: job.job_id || null })
      return
    }

    if (job.job_id) {
      this.setData({ jobId: job.job_id, status: '分析进行中...', loading: true })
      this._pollJob(job.job_id)
    } else {
      this.setData({ loading: false, status: '未返回任务 ID' })
    }
  },
  _pollJob(jobId) {
    setTimeout(() => {
      wx.request({
        url: `${API_BASE}/jobs/${jobId}`,
        method: 'GET',
        success: (res) => {
          this._handleJob(res.data || {})
        },
        fail: (err) => {
          console.error('poll job error', err)
          this.setData({ loading: false, status: '轮询失败', jobId })
        }
      })
    }, 1500)
  },
  updateCurrentItems() {
    const tabs = this.data.result.tabs || []
    const target = tabs.find((tab) => tab.id === this.data.activeTabId) || tabs[0] || { items: [] }
    const enriched = (target.items || []).map((item, index) => ({ ...item, _index: index }))
    this.setData({ currentItems: enriched })
  },
  onSwitchTab(e) {
    const id = e.currentTarget.dataset.id
    if (!id || id === this.data.activeTabId) return
    this.setData({ activeTabId: id }, () => {
      this.updateCurrentItems()
    })
  },
  onViewSource(e) {
    if (!this.data.hasSource || !this.data.jobId) {
      wx.showToast({ title: '原文暂不可用', icon: 'none' })
      return
    }
    const tabId = e.currentTarget.dataset.tab
    const index = Number(e.currentTarget.dataset.index)
    const tabs = this.data.result.tabs || []
    const tab = tabs.find((t) => t.id === tabId)
    if (!tab) return
    const item = (tab.items || [])[index]
    if (!item || item.source_start === null || item.source_start === undefined) {
      wx.showToast({ title: '缺少原文索引', icon: 'none' })
      return
    }
    const start = Number(item.source_start) || 0
    let end
    if (item.source_end !== null && item.source_end !== undefined) {
      end = Number(item.source_end)
    } else if (item.source_excerpt) {
      end = start + item.source_excerpt.length
    } else {
      end = start + 1
    }
    if (end <= start) end = start + 1

    wx.request({
      url: `${API_BASE}/jobs/${this.data.jobId}/source`,
      method: 'GET',
      data: { start, end, window: 200 },
      success: ({ data }) => {
        const excerpt = data.excerpt || item.source_excerpt || ''
        const context = data.context || excerpt
        this.setData({
          snippetVisible: true,
          snippetTitle: `${tab.title} · ${item.title}`,
          snippetMeta: `原文范围：${data.start} - ${data.end} ／ 全文 ${data.length} 字`,
          snippetContent: highlightContext(context, excerpt)
        })
      },
      fail: () => {
        wx.showToast({ title: '原文获取失败', icon: 'none' })
      }
    })
  },
  onCloseSnippet() {
    this.setData({ snippetVisible: false, snippetContent: '' })
  }
})
