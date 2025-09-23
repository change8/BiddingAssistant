const API_BASE = window.BIDDING_ASSISTANT_API || window.location.origin

const severityStyles = {
  critical: { text: '高风险', className: 'badge critical' },
  high: { text: '较高风险', className: 'badge high' },
  medium: { text: '中风险', className: 'badge medium' },
  low: { text: '低风险', className: 'badge low' }
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
      const title = hit.title || category
      hitNode.querySelector('.rule').textContent = title

      const badge = hitNode.querySelector('.severity')
      const cfg = severityStyles[hit.severity] || severityStyles.medium
      badge.textContent = cfg.text
      badge.className = cfg.className

      const summaryEl = hitNode.querySelector('.summary')
      summaryEl.textContent = hit.summary || hit.description || ''
      summaryEl.style.display = summaryEl.textContent ? 'block' : 'none'

      const evidenceEl = hitNode.querySelector('.evidence')
      evidenceEl.textContent = hit.evidence || ''
      evidenceEl.style.display = hit.evidence ? 'block' : 'none'

      const advice = hitNode.querySelector('.advice')
      advice.textContent = hit.recommendation ? `建议：${hit.recommendation}` : ''
      advice.style.display = hit.recommendation ? 'block' : 'none'

      list.appendChild(hitNode)
    })
    els.results.appendChild(catNode)
  }

  if (result.timeline && (result.timeline.milestones || result.timeline.remark)) {
    const timelineCard = document.createElement('div')
    timelineCard.className = 'timeline-card'
    const title = document.createElement('h3')
    title.textContent = '时间计划'
    timelineCard.appendChild(title)
    const list = document.createElement('ul')
    list.className = 'timeline-list'
    ;(result.timeline.milestones || []).forEach((m) => {
      const li = document.createElement('li')
      li.textContent = `${m.name || '节点'}${m.deadline ? ' · 截止：' + m.deadline : ''}${
        m.note ? ' · ' + m.note : ''
      }`
      list.appendChild(li)
    })
    if (list.childElementCount) timelineCard.appendChild(list)
    if (result.timeline.remark) {
      const remark = document.createElement('p')
      remark.textContent = `备注：${result.timeline.remark}`
      timelineCard.appendChild(remark)
    }
    els.results.appendChild(timelineCard)
  }
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
    }
    if (!data.job_id) {
      els.analyze.disabled = false
    }
    return
  }
  const result = data.result || data
  renderSummary(result.summary)
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
        const result = data.result || {}
        renderSummary(result.summary)
        renderResults(result)
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
      showProgress('正在分析文本...')
      els.analyze.disabled = true
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
