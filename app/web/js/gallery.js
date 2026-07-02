function renderProjectSummary(workspace){
  const el = $('#projectSummary');
  if(!el) return;
  if(!workspace || !workspace.active){
    el.textContent = 'Global workspace';
    return;
  }
  el.textContent = `${workspace.active.project_name}: ${workspace.outputs} outputs · ${workspace.references || 0} refs · ${workspace.prompts || 0} prompts · ${workspace.posepacks || 0} posepacks · ${workspace.quality || 0} QA · ${workspace.experiments} runs · ${workspace.queues} queues · ${workspace.releases || 0} releases`;
}

function renderOutputs(outputs){
  currentOutputs = outputs || [];
  if ($('#stat-outputs')) $('#stat-outputs').textContent = currentOutputs.length;
  const onboardingCard = document.getElementById('wizOnboardingCard');
  if (onboardingCard) {
    if (currentOutputs.length === 0) {
      document.getElementById('onboardingTitle').textContent = 'Ready for your first sprite?';
      document.getElementById('onboardingText').textContent = 'Click "Create Sprite" or launch the wizard below. We will guide you through character descriptions, action loops, and set up your ComfyUI generation automatically.';
      document.getElementById('onboardingCtaBtn').textContent = 'Launch Wizard';
    } else {
      document.getElementById('onboardingTitle').textContent = 'Continue Sprite Forge';
      document.getElementById('onboardingText').textContent = `You have generated ${currentOutputs.length} sprite(s) in this project workspace. Open the Quality Lab to review them or export your sprite sheets in the Release view.`;
      document.getElementById('onboardingCtaBtn').textContent = 'Create Another';
    }
  }
  const g=$('#gallery');
  clearNode(g);
  if(!currentOutputs.length){
    appendText(g, 'div', 'No sprite outputs yet. Run the demo or make a sprite.', 'empty');
    if (typeof renderGuidedGallery === 'function') renderGuidedGallery(currentOutputs);
    return;
  }
  currentOutputs.slice(0,12).forEach(o => {
    const card = document.createElement('article');
    card.className = 'sprite-card';
    card.dataset.path = o.path || '';
    const imgUrl = o.preview_url || o.sheet_url || '';
    if (imgUrl) {
      const img = document.createElement('img');
      img.src = `${imgUrl}?t=${Date.now()}`;
      img.alt = o.name || '';
      card.appendChild(img);
    } else {
      appendText(card, 'div', 'No preview', 'placeholder');
    }
    const meta = document.createElement('div');
    meta.className = 'meta';
    appendText(meta, 'b', o.name || '');
    appendText(meta, 'small', `${o.frame_count} frames · ${o.fps} fps · ${o.frame_width}×${o.frame_height}`);
    appendText(meta, 'small', o.modified || '');
    const actions = document.createElement('div');
    actions.className = 'button-row compact-actions';
    const review = document.createElement('button');
    review.type = 'button';
    review.className = 'mini primary';
    review.dataset.previewPath = o.path || '';
    review.textContent = 'Review';
    actions.appendChild(review);
    meta.appendChild(actions);
    card.appendChild(meta);
    g.appendChild(card);
  });
  $$('.sprite-card', g).forEach(card=>card.addEventListener('click',(e)=>{
    if (e.target.closest('[data-preview-path]')) return;
    selectedSpriteDir=card.dataset.path;
    $('#qualitySpriteDir').value=selectedSpriteDir;
    if($('#releaseSprites') && !$('#releaseSprites').value.includes(selectedSpriteDir)){
      $('#releaseSprites').value = ($('#releaseSprites').value ? $('#releaseSprites').value+'\n' : '') + selectedSpriteDir;
    }
    showView('quality');
    toast('Selected '+selectedSpriteDir);
    loadSpriteDetails(selectedSpriteDir);
  }));
  $$('[data-preview-path]', g).forEach(btn=>btn.addEventListener('click', e=>{
    e.stopPropagation();
    openResultPreview(e.currentTarget.dataset.previewPath);
  }));
  if (typeof renderGuidedGallery === 'function') renderGuidedGallery(currentOutputs);
}
async function loadSpriteDetails(path) {
  if (!path) return;
  try {
    const meta = await api('/file/' + path + '/sheet.json');
    $('#inspect-folder-name').textContent = path;
    $('#inspect-dimensions').textContent = `${meta.frame_width} × ${meta.frame_height}`;
    $('#inspect-frames-count').textContent = meta.frame_count;
    
    const scrub = $('#frameScrubber');
    scrub.min = 0;
    scrub.max = meta.frame_count - 1;
    scrub.value = 0;
    $('#frameScrubberLabel').textContent = `1 / ${meta.frame_count}`;
    
    window._currentMeta = meta;
    window._currentPath = path;
    
    // Fetch QA report if available
    let qa = null;
    try {
      qa = await api('/file/' + path + '/qa_report.json');
    } catch (e) {
      try {
        qa = await api('/file/' + path + '/quality_report.json');
      } catch (err) {}
    }
    window._currentQA = qa;
    
    // Populate QA panel details
    const loopRmse = $('#inspect-loop-rmse');
    const footStdev = $('#inspect-foot-stdev');
    const reportLink = $('#inspect-report-link');
    const driftContainer = $('#driftChartContainer');
    const coverageContainer = $('#coverageChartContainer');
    const issuesContainer = $('#inspect-issues');
    
    if (qa) {
      loopRmse.textContent = qa.metrics?.loop_seam_rmse !== undefined ? Number(qa.metrics.loop_seam_rmse).toFixed(1) : '—';
      footStdev.textContent = qa.metrics?.foot_y_stdev_px !== undefined ? Number(qa.metrics.foot_y_stdev_px).toFixed(2) + 'px' : '—';
      clearNode(reportLink);
      const reportAnchor = document.createElement('a');
      reportAnchor.href = `/file/${encodeURI(path)}/report.html`;
      reportAnchor.target = '_blank';
      reportAnchor.className = 'text-link';
      reportAnchor.textContent = 'Open Report';
      reportLink.appendChild(reportAnchor);
      
      // Draw SVG sparklines
      if (qa.frames) {
        const driftData = qa.frames.map(f => f.foot_y).filter(y => y !== undefined);
        clearNode(driftContainer);
        if (driftData.length > 1) driftContainer.appendChild(makeSparkline(driftData, '#ff4444'));
        else setTextState(driftContainer, 'Insufficient data', 'hint-text');
        
        const covData = qa.frames.map(f => f.alpha_coverage).filter(c => c !== undefined);
        clearNode(coverageContainer);
        if (covData.length > 1) coverageContainer.appendChild(makeSparkline(covData, '#00adb5'));
        else setTextState(coverageContainer, 'Insufficient data', 'hint-text');
      } else {
        driftContainer.textContent = 'No trend data';
        coverageContainer.textContent = 'No trend data';
      }
      
      // Draw Version Quality Trend Chart
      const trendContainer = $('#versionTrendChartContainer');
      if (trendContainer) {
        clearNode(trendContainer);
        api(`/api/sprite/version/list?path=${encodeURIComponent(path)}`).then(vres => {
          const versions = vres.versions || [];
          if (versions.length > 0) {
            const points = versions.map(v => {
              const m = v.metrics || {};
              return {
                label: v.label || v.id,
                drift: m.foot_y_stdev_px !== undefined ? m.foot_y_stdev_px : 0,
                seam: m.loop_seam_rmse !== undefined ? m.loop_seam_rmse : 0
              };
            });
            if (points.length > 1) {
              trendContainer.appendChild(makeMultiLineChart(points));
            } else {
              setTextState(trendContainer, 'Snapshot history will show trend lines.', 'hint-text');
            }
          } else {
            setTextState(trendContainer, 'No snapshots yet.', 'hint-text');
          }
        }).catch(err => {
          setTextState(trendContainer, 'No snapshot history found.', 'hint-text');
        });
      }
      
      // Populate dynamic alerts
      clearNode(issuesContainer);
      if (qa.issues && qa.issues.length > 0) {
        qa.issues.forEach(issue => {
          const badge = document.createElement('span');
          badge.className = `chip ${issue.level === 'error' ? 'warn' : 'info'}`;
          badge.classList.add('issue-chip');
          badge.textContent = `${issue.code}: ${issue.message}`;
          issuesContainer.appendChild(badge);
        });
      } else {
        setTextState(issuesContainer, 'Passed QA', 'pass-text');
      }
    } else {
      loopRmse.textContent = '—';
      footStdev.textContent = '—';
      reportLink.textContent = '—';
      setTextState(driftContainer, 'No QA data', 'hint-text');
      setTextState(coverageContainer, 'No QA data', 'hint-text');
      if ($('#versionTrendChartContainer')) setTextState($('#versionTrendChartContainer'), 'No QA data', 'hint-text');
      setTextState(issuesContainer, 'Run QA Report to analyze', 'hint-text');
    }

    
    // Check for sibling fixed/original folder for side-by-side comparison
    let siblingPath = '';
    if (path.endsWith('_fixed')) {
      siblingPath = path.slice(0, -6);
    } else {
      siblingPath = path + '_fixed';
    }
    window._siblingPath = siblingPath;
    window._siblingMeta = null;
    window._siblingImg = null;
    
    const siblingToggle = $('#toggleCompareSibling');
    if (siblingToggle) {
      siblingToggle.checked = false;
      siblingToggle.disabled = true;
      siblingToggle.parentElement.classList.add('is-disabled');
    }
    
    try {
      window._siblingMeta = await api('/file/' + siblingPath + '/sheet.json');
      const img = new Image();
      img.src = '/file/' + siblingPath + '/' + (window._siblingMeta.image || 'sheet.png') + '?t=' + Date.now();
      img.onload = () => {
        window._siblingImg = img;
        if (siblingToggle) {
          siblingToggle.disabled = false;
          siblingToggle.parentElement.classList.remove('is-disabled');
        }
      };
    } catch (e) {
      // Sibling not found
    }
    
    // Populate objective metrics
    const framesEl = $('#obj-metric-frames');
    const fpsEl = $('#obj-metric-fps');
    const loopEl = $('#obj-metric-loop');
    const driftEl = $('#obj-metric-drift');
    const exportEl = $('#obj-metric-export');

    if (framesEl) framesEl.textContent = `${meta.frame_count} frames`;
    if (fpsEl) fpsEl.textContent = `${meta.fps || 12} fps`;

    if (qa && qa.metrics) {
      const rmse = qa.metrics.loop_seam_rmse;
      if (rmse !== undefined && rmse !== null) {
        const loopScore = Math.max(0, Math.min(100, Math.round(100 - rmse * 2.5)));
        if (loopEl) loopEl.textContent = loopScore;
      } else {
        if (loopEl) loopEl.textContent = '—';
      }

      const stdev = qa.metrics.foot_y_stdev_px;
      if (stdev !== undefined && stdev !== null) {
        let classification = 'low';
        if (stdev >= 3.0) classification = 'high';
        else if (stdev >= 1.0) classification = 'moderate';
        if (driftEl) driftEl.textContent = classification;
      } else {
        if (driftEl) driftEl.textContent = '—';
      }
    } else {
      if (loopEl) loopEl.textContent = '—';
      if (driftEl) driftEl.textContent = '—';
    }

    const matchedOut = currentOutputs.find(o => o.path === path);
    const ready = matchedOut ? matchedOut.exports_ready : false;
    if (exportEl) {
      exportEl.textContent = ready ? 'ready' : 'pending';
      exportEl.style.color = ready ? '#56c590' : '#dc4d70';
    }

    frameEdits = [];
    if (typeof loadSpriteVersions === 'function') loadSpriteVersions(path);
    renderInspectorFrame(0);
  } catch (e) {
    console.error(e);
  }
}

function renderInspectorFrame(index) {
  const meta = window._currentMeta;
  const path = window._currentPath;
  if (!meta || !path) return;
  
  const frame = meta.frames ? meta.frames[index] : null;
  const fw = meta.frame_width;
  const fh = meta.frame_height;
  
  const img = new Image();
  img.src = '/file/' + path + '/' + (meta.image || 'sheet.png') + '?t=' + Date.now();
  img.onload = () => {
    let canvas = $('#inspector-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'inspector-canvas';
      canvas.className = 'inspector-img';
      const placeholder = $('#inspector-img');
      if (placeholder) {
        placeholder.replaceWith(canvas);
      } else {
        const container = $('#inspector-canvas-container');
        if (container) container.appendChild(canvas);
      }
    }
    
    const compare = $('#toggleCompareSibling') && $('#toggleCompareSibling').checked && window._siblingImg;
    canvas.width = compare ? fw * 2 : fw;
    canvas.height = fh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, fh);
    
    if (compare) {
      let imgLeft, imgRight, metaLeft, metaRight;
      if (path.endsWith('_fixed')) {
        imgLeft = window._siblingImg;
        metaLeft = window._siblingMeta;
        imgRight = img;
        metaRight = meta;
      } else {
        imgLeft = img;
        metaLeft = meta;
        imgRight = window._siblingImg;
        metaRight = window._siblingMeta;
      }
      
      let sxLeft = (index % metaLeft.columns) * fw;
      let syLeft = Math.floor(index / metaLeft.columns) * fh;
      const frameLeft = metaLeft.frames ? metaLeft.frames[index] : null;
      if (frameLeft) { sxLeft = frameLeft.x; syLeft = frameLeft.y; }
      
      let sxRight = (index % metaRight.columns) * fw;
      let syRight = Math.floor(index / metaRight.columns) * fh;
      const frameRight = metaRight.frames ? metaRight.frames[index] : null;
      if (frameRight) { sxRight = frameRight.x; syRight = frameRight.y; }
      
      ctx.drawImage(imgLeft, sxLeft, syLeft, fw, fh, 0, 0, fw, fh);
      ctx.drawImage(imgRight, sxRight, syRight, fw, fh, fw, 0, fw, fh);
    } else {
      let sx = (index % meta.columns) * fw;
      let sy = Math.floor(index / meta.columns) * fh;
      if (frame) { sx = frame.x; sy = frame.y; }
      ctx.drawImage(img, sx, sy, fw, fh, 0, 0, fw, fh);
    }
    
    if (frame && frame.bad) {
      ctx.fillStyle = 'rgba(255, 0, 0, 0.25)';
      ctx.fillRect(compare ? fw : 0, 0, fw, fh);
      ctx.fillStyle = '#ff4444';
      ctx.font = 'bold 16px sans-serif';
      ctx.fillText('BAD FRAME', (compare ? fw : 0) + 10, 25);
    }

    if (frame) {
      if ($('#pivotXInput')) $('#pivotXInput').value = frame.pivot_x !== undefined ? frame.pivot_x : Math.round(frame.w / 2);
      if ($('#pivotYInput')) $('#pivotYInput').value = frame.pivot_y !== undefined ? frame.pivot_y : frame.h;
    }
    
    $('#frameScrubberLabel').textContent = `${index + 1} / ${meta.frame_count}`;
    updateOverlays(fw, fh, index);
    if (typeof updateCompareOverlay === 'function') {
      updateCompareOverlay();
    }
  };
}

function updateOverlays(fw, fh, index) {
  const canvas = $('#inspector-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const compare = $('#toggleCompareSibling') && $('#toggleCompareSibling').checked && window._siblingImg;
  
  const showAnchor = $('#toggleAnchorOverlay') && $('#toggleAnchorOverlay').checked;
  const showBBox = $('#toggleBBoxOverlay') && $('#toggleBBoxOverlay').checked;
  
  const drawSideOverlays = (offset, meta, qaData) => {
    // Draw BBox
    if (showBBox && qaData && qaData.frames) {
      const fRecord = qaData.frames[index];
      if (fRecord && fRecord.bbox) {
        const [l, t, r, b] = fRecord.bbox;
        ctx.strokeStyle = 'rgba(0, 255, 128, 0.7)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(offset + l, t, r - l, b - t);
      }
    }
    
    // Draw Anchor Overlay
    if (showAnchor) {
      ctx.strokeStyle = 'rgba(255, 68, 68, 0.8)';
      ctx.lineWidth = 1.5;
      
      // Horizontal baseline at height - 4
      const by = fh - 4;
      ctx.beginPath();
      ctx.moveTo(offset, by);
      ctx.lineTo(offset + fw, by);
      ctx.stroke();
      
      // Vertical center line
      const cx = fw / 2;
      ctx.beginPath();
      ctx.moveTo(offset + cx, 0);
      ctx.lineTo(offset + cx, fh);
      ctx.stroke();
      
      // Small crosshair arc
      ctx.fillStyle = '#00adb5';
      ctx.beginPath();
      ctx.arc(offset + cx, by, 3.5, 0, 2 * Math.PI);
      ctx.fill();
    }
  };
  
  if (compare) {
    const path = window._currentPath;
    let qaLeft = null, qaRight = null;
    if (path.endsWith('_fixed')) {
      qaRight = window._currentQA;
    } else {
      qaLeft = window._currentQA;
    }
    drawSideOverlays(0, window._siblingMeta, qaLeft);
    drawSideOverlays(fw, window._currentMeta, qaRight);
  } else {
    drawSideOverlays(0, window._currentMeta, window._currentQA);
  }
}

if ($('#frameScrubber')) {
  $('#frameScrubber').addEventListener('input', (e) => {
    renderInspectorFrame(parseInt(e.target.value));
  });
}

const togglesList = ['#toggleAnchorOverlay', '#toggleBBoxOverlay', '#toggleCompareSibling'];
togglesList.forEach(sel => {
  const el = $(sel);
  if (el) {
    el.addEventListener('change', () => {
      const val = $('#frameScrubber').value;
      renderInspectorFrame(parseInt(val));
    });
  }
});

if ($('#toggleCheckerboard')) {
  $('#toggleCheckerboard').addEventListener('change', (e) => {
    const container = $('#inspector-canvas-container');
    if (e.target.checked) {
      container.classList.add('checkerboard');
    } else {
      container.classList.remove('checkerboard');
    }
  });
}
