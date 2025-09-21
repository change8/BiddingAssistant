const { API_BASE } = require('../../utils/config')

const severityMap = {
  critical: '高风险',
  high: '较高风险',
  medium: '中风险',
  low: '低风险'
}

function normalizeResult(result = {}) {
  const categories = result.categories || {}
  const normalized = {}
  Object.keys(categories).forEach((cat) => {
    normalized[cat] = (categories[cat] || []).map((item) => ({
      ...item,
      severityLabel: severityMap[item.severity] || item.severity,
      items: item.items || [],
      evidences: item.evidences || []
    }))
  })
  return {
    summary: result.summary || {},
    categories: normalized
  }
}

Page({
  data: {
    input: '',
    result: null,
    keys: [],
    summary: {},
    summaryKeys: [],
    jobId: null,
    status: '',
    loading: false
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
      result: null,
      keys: [],
      summary: {},
      summaryKeys: [],
      jobId: null
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
      const normalized = normalizeResult(job.result)
      const categories = normalized.categories || {}
      const summary = normalized.summary || {}
      const keys = Object.keys(categories)
      const summaryKeys = Object.keys(summary)
      this.setData({
        loading: false,
        status: '分析完成',
        result: normalized,
        keys,
        summary,
        summaryKeys,
        jobId: job.job_id || null
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
  }
})
