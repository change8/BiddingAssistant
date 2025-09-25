const API_BASE = window.BIDDING_ASSISTANT_API || window.location.origin

const priorityMap = {
  critical: '极高优先级',
  high: '高优先级',
  medium: '中优先级',
  low: '关注即可'
}

const els = {
  file: document.getElementById('fileInput'),
  fileName: document.getElementById('fileName'),
  text: document.getElementById('textInput'),
  analyze: document.getElementById('analyzeBtn'),
  clear: document.getElementById('clearBtn'),
  status: document.getElementById('status'),
  progress: document.getElementById('progress'),
  progressText: document.getElementById('progressText'),
  summary: document.getElementById('summary'),
  results: document.getElementById('results'),
  modal: document.getElementById('snippetModal'),
  modalTitle: document.getElementById('modalTitle'),
  modalMeta: document.getElementById('modalMeta'),
  modalContext: document.getElementById('modalContext'),
  modalClose: document.getElementById('modalClose')
}

const state = {
  jobId: null,
  tabs: [],
  activeTabId: null,
  hasSource: false,
  result: null
}

let pollTimer = null

function setStatus(message, type = 'info') {
  els.status.textContent = message
  els.status.classList.remove('hidden', 'error')
  if (type === 'error') {
    els.status.classList.add('error')
  }
}

function clearStatus() {
  els.status.classList.add('hidden')
  els.status.textContent = ''
  els.status.classList.remove('error')
}

function showProgress(message) {
  els.progressText.textContent = message
  els.progress.classList.remove('hidden')
}

function hideProgress() {
  els.progress.classList.add('hidden')
}

function closeModal() {
  if (!els.modal) return
  els.modal.classList.add('hidden')
  if (els.modalContext) els.modalContext.textContent = ''
  if (els.modalMeta) els.modalMeta.textContent = ''
}

function clearResults() {
  state.jobId = null
  state.tabs = []
  state.activeTabId = null
  state.hasSource = false
  state.result = null
  els.summary.innerHTML = ''
  els.results.innerHTML = ''
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  closeModal()
}

function renderSummary(text) {
  els.summary.innerHTML = ''
  const div = document.createElement('div')
  div.className = 'summary-text'
  div.textContent = text || '模型未提供整体概述，可参考下方分类提示。'
  els.summary.appendChild(div)
}

function normaliseTab(tab) {
  if (!tab || typeof tab !== 'object') return null
  const items = Array.isArray(tab.items)
    ? tab.items.filter((item) => item && typeof item === 'object')
    : []
  const id = String(tab.id || '').trim()
  if (!id) return null
  const title = tab.title || tab.name || id
  return { id, title, items }
}

function renderResults(jobId, result, hasSource = false) {
  state.jobId = jobId || state.jobId
  state.result = result || {}
  state.hasSource = Boolean(hasSource)
  const tabs = Array.isArray(state.result.tabs) ? state.result.tabs.map(normaliseTab).filter(Boolean) : []
  state.tabs = tabs
  if (state.tabs.length === 0) {
    state.activeTabId = null
  } else if (!state.activeTabId || !state.tabs.some((tab) => tab.id === state.activeTabId)) {
    state.activeTabId = state.tabs[0].id
  }

  renderSummary(state.result.summary || '')
  renderTabs()
}

function renderTabs() {
  els.results.innerHTML = ''
  if (!state.tabs.length) {
    els.results.appendChild(createHint('暂无分类结果，建议人工核查。'))
    return
  }

  const nav = document.createElement('div')
  nav.className = 'tabs-nav'
  state.tabs.forEach((tab) => {
    const btn = document.createElement('button')
    btn.type = 'button'
    const count = Array.isArray(tab.items) ? tab.items.length : 0
    btn.textContent = `${tab.title || tab.id} (${count})`
    btn.className = `tab-btn${tab.id === state.activeTabId ? ' active' : ''}`
    btn.addEventListener('click', () => {
      state.activeTabId = tab.id
      renderTabs()
    })
    nav.appendChild(btn)
  })
  els.results.appendChild(nav)

  const content = document.createElement('div')
  content.className = 'tab-content'
  els.results.appendChild(content)
  renderTabContent(content)
}

function renderTabContent(container) {
  const tab = state.tabs.find((t) => t.id === state.activeTabId)
  if (!tab) {
    container.appendChild(createHint('请选择分类标签。'))
    return
  }
  const items = Array.isArray(tab.items) ? tab.items : []
  if (!items.length) {
    container.appendChild(createHint('该分类暂无模型输出，建议人工确认。'))
    return
  }
  items.forEach((item) => {
    container.appendChild(createItemCard(tab, item))
  })
}

function createHint(text) {
  const span = document.createElement('span')
  span.className = 'empty-hint'
  span.textContent = text
  return span
}

function createItemCard(tab, item) {
  const card = document.createElement('div')
  card.className = 'item-card'

  const header = document.createElement('div')
  header.className = 'item-header'
  const title = document.createElement('span')
  title.textContent = item.title || item.milestone || item.event || '要点'
  header.appendChild(title)

  const { level, label } = normalisePriority(item.priority)
  const priority = document.createElement('span')
  priority.className = `priority-pill ${level}`
  priority.textContent = label
  header.appendChild(priority)
  card.appendChild(header)

  const body = document.createElement('div')
  body.className = 'item-body'
  appendInfoRow(body, '为何重要', item.why_important || item.reason || item.summary)
  appendInfoRow(body, '行动建议', item.guidance || item.action || item.recommendation)

  if (tab.id === 'bid_timeline') {
    appendInfoRow(body, '关键节点', item.milestone || item.title)
    appendInfoRow(body, '时间', item.date || item.deadline)
  } else {
    appendInfoRow(body, '补充说明', item.details || item.notes || item.impact)
  }

  if (item.source_excerpt) {
    const excerpt = document.createElement('div')
    excerpt.className = 'item-excerpt'
    excerpt.textContent = item.source_excerpt
    body.appendChild(excerpt)
  }

  card.appendChild(body)

  const actions = document.createElement('div')
  actions.className = 'source-actions'
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'source-link'

  if (canOpenSource(item)) {
    btn.textContent = '查看原文'
    btn.addEventListener('click', () => openSourceSnippet(tab, item))
  } else {
    btn.textContent = state.hasSource ? '缺少索引' : '原文暂不可用'
    btn.disabled = true
    btn.style.opacity = '0.6'
  }
  actions.appendChild(btn)
  card.appendChild(actions)

  return card
}

function appendInfoRow(container, labelText, value) {
  if (!value) return
  const row = document.createElement('div')
  row.className = 'info-row'
  const label = document.createElement('span')
  label.className = 'label'
  label.textContent = `${labelText}：`
  row.appendChild(label)
  row.appendChild(document.createTextNode(value))
  container.appendChild(row)
}

function normalisePriority(priority) {
  const level = (priority || 'medium').toLowerCase()
  return {
    level: ['critical', 'high', 'medium', 'low'].includes(level) ? level : 'medium',
    label: priorityMap[level] || priorityMap.medium
  }
}

function canOpenSource(item) {
  const start = Number(item.source_start)
  return state.hasSource && Number.isFinite(start)
}

function getSourceRange(item) {
  const startVal = Number(item.source_start)
  const start = Number.isFinite(startVal) ? startVal : 0
  let end
  const endVal = Number(item.source_end)
  if (Number.isFinite(endVal)) {
    end = endVal
  } else if (item.source_excerpt) {
    end = start + item.source_excerpt.length
  } else {
    end = start + 1
  }
  if (end <= start) end = start + 1
  return { start: Math.max(0, start), end }
}

async function openSourceSnippet(tab, item) {
  if (!canOpenSource(item) || !state.jobId) return
  const range = getSourceRange(item)
  const params = new URLSearchParams({
    start: String(range.start),
    end: String(range.end),
    window: '200'
  })
  try {
    const resp = await fetch(`${API_BASE}/jobs/${state.jobId}/source?${params.toString()}`)
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(text || `HTTP ${resp.status}`)
    }
    const data = await resp.json()
    showSnippetModal(tab, item, data)
  } catch (err) {
    setStatus(err.message || '原文获取失败', 'error')
  }
}

function showSnippetModal(tab, item, snippet) {
  if (!els.modal) return
  const titlePieces = [tab.title || tab.id]
  const itemTitle = item.title || item.milestone || item.event
  if (itemTitle) titlePieces.push(itemTitle)
  if (els.modalTitle) els.modalTitle.textContent = titlePieces.join(' · ')
  if (els.modalMeta) {
    els.modalMeta.textContent = `原文范围：${snippet.start} - ${snippet.end} ／ 全文 ${snippet.length} 字`
  }
  if (els.modalContext) {
    const excerpt = snippet.excerpt || item.source_excerpt || ''
    const context = snippet.context || excerpt
    els.modalContext.innerHTML = highlightContext(context, excerpt)
  }
  els.modal.classList.remove('hidden')
}

function highlightContext(context, excerpt) {
  const source = context || ''
  const target = excerpt || ''
  if (!target) {
    return escapeHTML(source)
  }
  let index = source.indexOf(target)
  let highlightText = target
  if (index === -1) {
    const trimmed = target.trim()
    if (trimmed) {
      index = source.indexOf(trimmed)
      highlightText = trimmed
    }
  }
  if (index === -1) {
    return `${escapeHTML(source)}\n\n（未能精确定位摘录，已显示上下文）`
  }
  const before = escapeHTML(source.slice(0, index))
  const match = escapeHTML(source.slice(index, index + highlightText.length))
  const after = escapeHTML(source.slice(index + highlightText.length))
  return `${before}<mark>${match}</mark>${after}`
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

async function analyzeText(text) {
  const payload = { text }
  showProgress('正在分析文本...')
  els.analyze.disabled = true
  const resp = await fetch(`${API_BASE}/analyze/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  await handleJobResponse(resp)
}

async function analyzeFile(file) {
  const form = new FormData()
  form.append('file', file)
  form.append('async_mode', 'true')
  showProgress('正在上传文件并解析内容...')
  els.analyze.disabled = true
  const resp = await fetch(`${API_BASE}/analyze/file`, {
    method: 'POST',
    body: form
  })
  await handleJobResponse(resp)
}

async function handleJobResponse(resp) {
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(text || `HTTP ${resp.status}`)
  }
  const data = await resp.json()
  const hasSource = Boolean(data.has_source_text)
  if (data.status && !data.result) {
    showProgress('模型分析中...')
    if (data.job_id) {
      pollJob(data.job_id)
      state.jobId = data.job_id
    } else {
      els.analyze.disabled = false
    }
    return
  }
  const result = data.result || data
  renderResults(data.job_id || state.jobId, result, hasSource)
  setStatus('分析完成 ✅')
  hideProgress()
  els.analyze.disabled = false
}

async function pollJob(jobId) {
  pollTimer = setTimeout(async () => {
    try {
      const resp = await fetch(`${API_BASE}/jobs/${jobId}`)
      if (!resp.ok) throw new Error(`轮询失败 ${resp.status}`)
      const data = await resp.json()
      if (data.status === 'completed') {
        clearTimeout(pollTimer)
        pollTimer = null
        renderResults(jobId, data.result || {}, Boolean(data.has_source_text))
        setStatus('分析完成 ✅')
        hideProgress()
        els.analyze.disabled = false
      } else if (data.status === 'failed') {
        clearTimeout(pollTimer)
        pollTimer = null
        setStatus(data.error || '分析失败', 'error')
        hideProgress()
        els.analyze.disabled = false
      } else {
        pollJob(jobId)
      }
    } catch (err) {
      clearTimeout(pollTimer)
      pollTimer = null
      setStatus(err.message, 'error')
      hideProgress()
      els.analyze.disabled = false
    }
  }, 1600)
}

els.analyze.addEventListener('click', async () => {
  clearStatus()
  clearResults()
  const file = els.file.files[0]
  const text = els.text.value.trim()
  try {
    if (file) {
      setStatus(`正在处理：${file.name}`)
      await analyzeFile(file)
    } else if (text) {
      await analyzeText(text)
    } else {
      setStatus('请先上传文件或粘贴文本', 'error')
    }
  } catch (err) {
    setStatus(err.message || '请求失败', 'error')
    hideProgress()
    els.analyze.disabled = false
  }
})

els.clear.addEventListener('click', () => {
  if (els.file) els.file.value = ''
  if (els.fileName) els.fileName.textContent = '尚未选择文件'
  if (els.text) els.text.value = ''
  clearResults()
  clearStatus()
  hideProgress()
  els.analyze.disabled = false
})

if (els.file) {
  els.file.addEventListener('change', () => {
    const file = els.file.files[0]
    if (els.fileName) {
      els.fileName.textContent = file
        ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`
        : '尚未选择文件'
    }
  })
}

if (els.modalClose) {
  els.modalClose.addEventListener('click', closeModal)
}

if (els.modal) {
  els.modal.addEventListener('click', (event) => {
    if (event.target === els.modal) {
      closeModal()
    }
  })
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeModal()
  }
})
