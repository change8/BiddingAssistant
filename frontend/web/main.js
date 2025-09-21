const API_BASE = window.BIDDING_ASSISTANT_API || window.location.origin

const severityStyles = {
  critical: { text: '高风险', className: 'badge critical' },
  high: { text: '较高风险', className: 'badge high' },
  medium: { text: '中风险', className: 'badge medium' },
  low: { text: '低风险', className: 'badge low' }
}

const ruleDescriptions = new Map()
fetch(`${API_BASE}/rules`)
  .then((resp) => (resp.ok ? resp.json() : Promise.reject()))
  .then((data) => {
    for (const item of data.rules || []) {
      ruleDescriptions.set(item.id, item.description)
    }
  })
  .catch(() => {
    /* 忽略规则列表请求失败 */
  })

const els = {
  file: document.getElementById('fileInput'),
  text: document.getElementById('textInput'),
  analyze: document.getElementById('analyzeBtn'),
  clear: document.getElementById('clearBtn'),
  status: document.getElementById('status'),
  summary: document.getElementById('summary'),
  results: document.getElementById('results'),
  catTemplate: document.getElementById('categoryTemplate'),
  hitTemplate: document.getElementById('hitTemplate')
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

function clearResults() {
  els.summary.innerHTML = ''
  els.results.innerHTML = ''
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function renderSummary(summary = {}) {
  els.summary.innerHTML = ''
  const entries = Object.entries(summary)
  if (!entries.length) return
  for (const [category, count] of entries) {
    const tag = document.createElement('span')
    tag.className = 'tag'
    tag.textContent = `${category} · ${count}`
    els.summary.appendChild(tag)
  }
}

function renderResults(result) {
  els.results.innerHTML = ''
  if (!result || !result.categories) return
  for (const [category, items] of Object.entries(result.categories)) {
    const catNode = els.catTemplate.content.cloneNode(true)
    const details = catNode.querySelector('details')
    const summary = catNode.querySelector('summary')
    const list = catNode.querySelector('.hit-list')
    summary.textContent = `${category}（${items.length}）`

    items.forEach((hit) => {
      const hitNode = els.hitTemplate.content.cloneNode(true)
      const ruleName = hit.description || ruleDescriptions.get(hit.rule_id) || hit.rule_id
      hitNode.querySelector('.rule').textContent = ruleName

      const badge = hitNode.querySelector('.severity')
      const cfg = severityStyles[hit.severity] || severityStyles.medium
      badge.textContent = cfg.text
      badge.className = cfg.className
      hitNode.querySelector('.snippet').textContent = hit.snippet || hit.evidence || ''
      const advice = hitNode.querySelector('.advice')
      advice.textContent = hit.advice ? `建议：${hit.advice}` : ''
      list.appendChild(hitNode)
    })
    els.results.appendChild(catNode)
  }
}

async function analyzeText(text) {
  const payload = { text }
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
    setStatus('任务处理中，请稍候...')
    if (data.job_id) {
      pollJob(data.job_id)
    }
    return
  }
  const result = data.result || data
  renderSummary(result.summary)
  renderResults(result)
  setStatus('分析完成 ✅')
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
        const result = data.result || {}
        renderSummary(result.summary)
        renderResults(result)
        setStatus('分析完成 ✅')
      } else if (data.status === 'failed') {
        clearTimeout(pollTimer)
        pollTimer = null
        setStatus(data.error || '分析失败', 'error')
      } else {
        pollJob(jobId)
      }
    } catch (err) {
      clearTimeout(pollTimer)
      pollTimer = null
      setStatus(err.message, 'error')
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
      setStatus(`正在上传 ${file.name} ...`)
      await analyzeFile(file)
    } else if (text) {
      setStatus('正在分析文本...')
      await analyzeText(text)
    } else {
      setStatus('请先上传文件或粘贴文本', 'error')
    }
  } catch (err) {
    setStatus(err.message || '请求失败', 'error')
  }
})

els.clear.addEventListener('click', () => {
  els.file.value = ''
  els.text.value = ''
  clearResults()
  clearStatus()
})
