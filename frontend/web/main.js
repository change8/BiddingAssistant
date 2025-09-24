const API_BASE = window.BIDDING_ASSISTANT_API || window.location.origin

const severityMap = {
  critical: '高风险',
  high: '较高风险',
  medium: '中风险',
  low: '低风险'
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
  results: document.getElementById('results')
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

function clearResults() {
  els.summary.innerHTML = ''
  els.results.innerHTML = ''
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function renderSummary(text) {
  els.summary.innerHTML = ''
  const div = document.createElement('div')
  div.className = 'summary-text'
  div.textContent = text || '模型未提供整体概述，可参考下方详细信息。'
  els.summary.appendChild(div)
}

function appendCard(card) {
  els.results.appendChild(card)
}

function createSectionCard(title) {
  const card = document.createElement('div')
  card.className = 'results-card'
  const h3 = document.createElement('h3')
  h3.textContent = title
  card.appendChild(h3)
  return card
}

function renderCriticalRequirements(data = []) {
  if (!data.length) return
  const card = createSectionCard('关键/强制要求')
  data.forEach((group) => {
    const wrapper = document.createElement('div')
    wrapper.className = 'critical-category'
    const h4 = document.createElement('h4')
    h4.textContent = group.category || '分类'
    wrapper.appendChild(h4)
    (group.items || []).forEach((item) => {
      const itemNode = document.createElement('div')
      itemNode.className = 'critical-item'
      const header = document.createElement('header')
      const title = document.createElement('span')
      title.textContent = item.title || '要点'
      const severity = document.createElement('span')
      const level = (item.severity || 'medium').toLowerCase()
      severity.className = `severity-pill ${level}`
      severity.textContent = severityMap[level] || level
      header.appendChild(title)
      header.appendChild(severity)
      itemNode.appendChild(header)

      if (item.description) {
        const desc = document.createElement('div')
        desc.textContent = item.description
        itemNode.appendChild(desc)
      }
      if (item.impact) {
        const impact = document.createElement('div')
        impact.className = 'label'
        impact.textContent = `影响：${item.impact}`
        itemNode.appendChild(impact)
      }
      if (item.action_required) {
        const action = document.createElement('div')
        action.className = 'label'
        action.textContent = `行动建议：${item.action_required}`
        itemNode.appendChild(action)
      }
      if (item.evidence) {
        const evidence = document.createElement('div')
        evidence.className = 'evidence-box'
        evidence.textContent = item.evidence
        itemNode.appendChild(evidence)
      }
      wrapper.appendChild(itemNode)
    })
    card.appendChild(wrapper)
  })
  appendCard(card)
}

function renderCostFactors(data = []) {
  if (!data.length) return
  const card = createSectionCard('成本/商务影响')
  const list = document.createElement('div')
  list.className = 'list-grid'
  data.forEach((item) => {
    const node = document.createElement('div')
    node.className = 'list-item'
    const title = document.createElement('strong')
    title.textContent = item.item || '成本因素'
    node.appendChild(title)
    if (item.description) {
      const desc = document.createElement('div')
      desc.textContent = item.description
      node.appendChild(desc)
    }
    if (item.estimated_impact) {
      const impact = document.createElement('div')
      impact.className = 'label'
      impact.textContent = `影响：${item.estimated_impact}`
      node.appendChild(impact)
    }
    if (item.evidence) {
      const evidence = document.createElement('div')
      evidence.className = 'evidence-box'
      evidence.textContent = item.evidence
      node.appendChild(evidence)
    }
    list.appendChild(node)
  })
  card.appendChild(list)
  appendCard(card)
}

function renderTimeline(data = []) {
  if (!data.length) return
  const card = createSectionCard('时间计划')
  const list = document.createElement('ul')
  list.className = 'timeline-list'
  data.forEach((item) => {
    const li = document.createElement('li')
    li.className = 'timeline-entry'
    const name = document.createElement('strong')
    name.textContent = item.event || item.name || '关键节点'
    li.appendChild(name)
    const info = document.createElement('span')
    info.textContent = `${item.deadline ? `截止：${item.deadline}` : ''}${item.importance ? ` · ${item.importance}` : ''}`
    li.appendChild(info)
    list.appendChild(li)
  })
  card.appendChild(list)
  appendCard(card)
}

function renderRisks(data = []) {
  if (!data.length) return
  const card = createSectionCard('风险与应对')
  const list = document.createElement('div')
  list.className = 'list-grid'
  data.forEach((item) => {
    const node = document.createElement('div')
    node.className = 'list-item'
    const title = document.createElement('strong')
    title.textContent = item.type || '风险'
    node.appendChild(title)
    if (item.description) {
      const desc = document.createElement('div')
      desc.textContent = item.description
      node.appendChild(desc)
    }
    const meta = document.createElement('div')
    meta.className = 'label'
    meta.textContent = `可能性：${item.likelihood || 'unknown'} · 影响：${item.impact || 'unknown'}`
    node.appendChild(meta)
    if (item.mitigation) {
      const mitigation = document.createElement('div')
      mitigation.className = 'label'
      mitigation.textContent = `应对：${item.mitigation}`
      node.appendChild(mitigation)
    }
    list.appendChild(node)
  })
  card.appendChild(list)
  appendCard(card)
}

function renderUnusualFindings(data = []) {
  if (!data.length) return
  const card = createSectionCard('特殊发现')
  const list = document.createElement('div')
  list.className = 'list-grid'
  data.forEach((item) => {
    const node = document.createElement('div')
    node.className = 'list-item'
    const title = document.createElement('strong')
    title.textContent = item.title || '特殊点'
    node.appendChild(title)
    if (item.description) {
      const desc = document.createElement('div')
      desc.textContent = item.description
      node.appendChild(desc)
    }
    if (item.concern) {
      const concern = document.createElement('div')
      concern.className = 'label'
      concern.textContent = `关注点：${item.concern}`
      node.appendChild(concern)
    }
    if (item.suggestion) {
      const suggestion = document.createElement('div')
      suggestion.className = 'label'
      suggestion.textContent = `建议：${item.suggestion}`
      node.appendChild(suggestion)
    }
    list.appendChild(node)
  })
  card.appendChild(list)
  appendCard(card)
}

function renderClarifications(data = []) {
  if (!data.length) return
  const card = createSectionCard('澄清问题')
  const list = document.createElement('div')
  list.className = 'list-grid'
  data.forEach((item) => {
    const node = document.createElement('div')
    node.className = 'list-item'
    const title = document.createElement('strong')
    title.textContent = item.issue || '问题'
    node.appendChild(title)
    if (item.context) {
      const ctx = document.createElement('div')
      ctx.textContent = item.context
      node.appendChild(ctx)
    }
    if (item.suggested_question) {
      const q = document.createElement('div')
      q.className = 'label'
      q.textContent = `建议提问：${item.suggested_question}`
      node.appendChild(q)
    }
    list.appendChild(node)
  })
  card.appendChild(list)
  appendCard(card)
}

function renderResults(result) {
  els.results.innerHTML = ''
  if (!result) {
    const span = document.createElement('span')
    span.className = 'empty-hint'
    span.textContent = '未获得分析结果。'
    els.results.appendChild(span)
    return
  }

  renderSummary(result.summary)
  renderCriticalRequirements(result.critical_requirements)
  renderCostFactors(result.cost_factors)
  renderTimeline(result.timeline)
  renderRisks(result.risks)
  renderUnusualFindings(result.unusual_findings)
  renderClarifications(result.clarification_needed)
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
  return await handleJobResponse(resp)
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
  return await handleJobResponse(resp)
}

async function handleJobResponse(resp) {
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(text || `HTTP ${resp.status}`)
  }
  const data = await resp.json()
  if (data.status && !data.result) {
    showProgress('模型分析中...')
    if (data.job_id) {
      pollJob(data.job_id)
    } else {
      els.analyze.disabled = false
    }
    return
  }
  const result = data.result || data
  renderResults(result)
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
        renderResults(data.result || {})
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
  els.file.value = ''
  if (els.fileName) els.fileName.textContent = '尚未选择文件'
  els.text.value = ''
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
