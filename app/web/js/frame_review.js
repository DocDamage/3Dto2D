function frameReviewCurrentIndex() {
  return Number($('#frameScrubber')?.value || 0);
}

function frameReviewCurrentFrame() {
  const meta = window._currentMeta;
  const idx = frameReviewCurrentIndex();
  return meta?.frames?.[idx] || null;
}

function frameReviewSummary(meta) {
  const counts = { approved: 0, rejected: 0, needs_edit: 0, unreviewed: 0 };
  (meta?.frames || []).forEach(frame => {
    const status = frame.review_status || 'unreviewed';
    counts[counts[status] === undefined ? 'unreviewed' : status] += 1;
  });
  return counts;
}

function updateFrameReviewUi() {
  const frame = frameReviewCurrentFrame();
  const status = frame?.review_status || 'unreviewed';
  $$('.frame-review-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.status === status));
  const note = $('#frameReviewNote');
  if (note && document.activeElement !== note) note.value = frame?.review_note || '';
  const counts = frameReviewSummary(window._currentMeta);
  const summary = $('#frameReviewSummary');
  if (summary) {
    summary.textContent = `${counts.approved} approved · ${counts.needs_edit} needs edit · ${counts.rejected} rejected`;
  }
}

async function setFrameReviewStatus(status) {
  const meta = window._currentMeta;
  const path = window._currentPath;
  const idx = frameReviewCurrentIndex();
  if (!meta || !path) {
    toast('Select a sprite first.');
    return;
  }
  const note = $('#frameReviewNote')?.value || '';
  const res = await api('/api/sprite/frame/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ path, frame_index: idx, status, note }),
  });
  if (res.ok) {
    meta.frames[idx].review_status = status;
    if (note) meta.frames[idx].review_note = note;
    else if (status === 'approved') delete meta.frames[idx].review_note;
    updateFrameReviewUi();
    toast(`Frame ${idx + 1} marked ${status.replace('_', ' ')}.`);
  }
}

function installFrameReview() {
  if ($('#frameReviewPanel') || !$('#inspector-card')) return;
  const panel = document.createElement('section');
  panel.id = 'frameReviewPanel';
  panel.className = 'frame-review-panel';
  panel.innerHTML = `
    <p class="eyebrow">Frame Approval</p>
    <div class="frame-review-actions">
      <button type="button" class="mini frame-review-btn" data-status="approved">Approve</button>
      <button type="button" class="mini frame-review-btn" data-status="needs_edit">Needs Edit</button>
      <button type="button" class="mini frame-review-btn danger" data-status="rejected">Reject</button>
    </div>
    <input id="frameReviewNote" placeholder="Optional frame note" />
    <small id="frameReviewSummary">0 approved · 0 needs edit · 0 rejected</small>
  `;
  const controls = $('.inspector-controls');
  if (controls) controls.prepend(panel);
  $$('.frame-review-btn', panel).forEach(btn => {
    btn.addEventListener('click', () => setFrameReviewStatus(btn.dataset.status));
  });
  $('#frameScrubber')?.addEventListener('input', updateFrameReviewUi);
  if (!window._frameReviewWrappedRender && typeof renderInspectorFrame === 'function') {
    const baseRender = renderInspectorFrame;
    window._frameReviewWrappedRender = true;
    const wrapped = function wrappedRenderInspectorFrame(index) {
      baseRender(index);
      setTimeout(updateFrameReviewUi, 0);
    };
    renderInspectorFrame = wrapped;
  }
  updateFrameReviewUi();
}

installFrameReview();
