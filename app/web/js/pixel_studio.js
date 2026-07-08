// Pixel Studio UI Logic Module - Phase 1 to 12 Full Integration
(function () {
  let zoom = 400;
  let gridOn = true;
  let seamPreviewOn = false;
  let activeAsset = null; // Currently selected asset metadata object
  let activeBatch = null; // Active batch manifest if multi-direction or tileset
  let styleProfiles = [];
  let pixelRecipes = [];
  let pixelModeConfigs = {};
  let pixelProviderCapabilities = {};
  let activeProviderCapability = null;
  let currentCompareMode = 'normalized'; // 'normalized', 'raw', 'transferred', 'source'
  let currentViewMode = 'sheet'; // 'sheet' or 'single'

  // Editor states (Phase 7 & 8)
  let isEditing = false;
  let currentTool = 'pencil'; // pencil, eraser, bucket, picker, line, rectangle, select, move, mask
  let activeColor = '#ffffff';
  let drawing = false;
  let undoStack = [];
  let redoStack = [];
  let editorDragStart = null;
  let editorPreviewState = null;
  let editorSelection = null;
  let editorMovedSelection = null;
  let inpaintCompareSnapshot = null;
  let inpaintCompareToken = 0;

  // Animation player states (Phase 9 & 10)
  let activeAnimation = null;
  let isPlaying = false;
  let animInterval = null;
  let currentFrameIdx = 0;

  // Rigging states (Phase 11)
  let activeRigKeyframe = 0; // 0 (Pose A) or 1 (Pose B)
  let rigKeyframes = [
    { time: 0.0, angles: { head: 0, arm_left: 0, arm_right: 0 } },
    { time: 1.0, angles: { head: 10, arm_left: 45, arm_right: -45 } }
  ];

  // Pack Builder states (Phase 12)
  let activePack = null;

  function initPixelStudio() {
    const viewEl = $('#view-pixel_studio');
    if (!viewEl) return;

    // Bind Mode tab clicks
    $$('[data-mode-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (isEditing) {
          toast("Please exit or save edit mode before switching tabs.");
          return;
        }

        $$('[data-mode-tab]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.dataset.modeTab;
        $('#pixelActiveMode').value = mode;
        
        const promptPlaceholderMap = {
          characters: "single full-body game character sprite, rogue adventurer with blue hood, leather armor",
          creatures: "single forest slime creature sprite, green glowing gelatinous body, big cute eyes",
          items: "magical gold key icon, glowing blue aura, ancient details",
          weapons: "epic flaming ruby sword icon, detailed hilt, glowing lava blade",
          potions: "health potion bottle icon, bubbling red liquid, cork stopper",
          ui_icons: "retro wooden setting button icon, bronze gear center",
          tilesets: "dark stone brick dungeon floor, seamless tiling texture, cracks and moss",
          backgrounds: "sunset sky parallax layer with distant low-poly purple mountains"
        };
        $('#pixelPrompt').placeholder = promptPlaceholderMap[mode] || "Enter description...";
        renderModeOptions(mode);

        // Toggle tileset generator settings (Phase 6)
        const tilesetSection = $('#pixelTilesetSettingsSection');
        const directionsLabel = $('#pixelDirectionsLabel');
        const batchCountLabel = $('#pixelBatchCountLabel');

        if (mode === 'tilesets') {
          if (tilesetSection) tilesetSection.style.display = 'block';
          if (directionsLabel) directionsLabel.style.display = 'none';
          if (batchCountLabel) batchCountLabel.style.display = 'none';
        } else {
          if (tilesetSection) tilesetSection.style.display = 'none';
          if (directionsLabel) directionsLabel.style.display = 'block';
          
          const dirSelect = $('#pixelDirectionsSelect');
          if (dirSelect && dirSelect.value === '1') {
            if (batchCountLabel) batchCountLabel.style.display = 'block';
          } else {
            if (batchCountLabel) batchCountLabel.style.display = 'none';
          }
        }
      });
    });

    // Toggle Batch Count visibility based on Directions
    const directionsSelect = $('#pixelDirectionsSelect');
    const batchCountLabel = $('#pixelBatchCountLabel');
    if (directionsSelect && batchCountLabel) {
      directionsSelect.addEventListener('change', () => {
        const count = directionsSelect.value;
        if (count === '1' && $('#pixelActiveMode').value !== 'tilesets') {
          batchCountLabel.style.display = 'block';
        } else {
          batchCountLabel.style.display = 'none';
        }
      });
    }

    $$('[data-pixel-workflow]').forEach(btn => {
      btn.addEventListener('click', () => applyPixelWorkflow(btn.dataset.pixelWorkflow));
    });

    const failureDismissBtn = $('#pixelFailureDismissBtn');
    if (failureDismissBtn) {
      failureDismissBtn.addEventListener('click', () => {
        const panel = $('#pixelFailurePanel');
        if (panel) panel.style.display = 'none';
      });
    }

    // Zoom Controls
    const zoomInBtn = $('#pixelZoomInBtn');
    const zoomOutBtn = $('#pixelZoomOutBtn');
    const gridToggleBtn = $('#pixelGridToggleBtn');
    const seamPreviewBtn = $('#pixelSeamPreviewBtn');
    const spriteContainer = $('#pixelSpriteContainer');
    const gridOverlay = $('#pixelGridOverlay');

    if (zoomInBtn && zoomOutBtn) {
      zoomInBtn.addEventListener('click', () => {
        if (zoom < 1600) zoom += 100;
        updateZoom();
      });
      zoomOutBtn.addEventListener('click', () => {
        if (zoom > 100) zoom -= 100;
        updateZoom();
      });
    }

    if (gridToggleBtn) {
      gridToggleBtn.addEventListener('click', () => {
        gridOn = !gridOn;
        gridToggleBtn.textContent = `Grid: ${gridOn ? 'ON' : 'OFF'}`;
        gridOverlay.style.display = gridOn ? 'block' : 'none';
      });
    }

    if (seamPreviewBtn) {
      seamPreviewBtn.addEventListener('click', () => {
        seamPreviewOn = !seamPreviewOn;
        seamPreviewBtn.textContent = `Seam Preview: ${seamPreviewOn ? 'ON' : 'OFF'}`;
        
        // Hide grid overlay when seam preview is ON to check tile seams clearly
        if (gridOverlay) {
          gridOverlay.style.display = (gridOn && !seamPreviewOn) ? 'block' : 'none';
        }
        syncComparePreview();
      });
    }

    function updateZoom() {
      if (spriteContainer) {
        spriteContainer.style.transform = `scale(${zoom / 100})`;
      }
      const zoomLevelEl = $('#pixelZoomLevel');
      if (zoomLevelEl) {
        zoomLevelEl.textContent = `${zoom}%`;
      }
    }

    // Load styles & LoRAs on launch
    loadModeConfigs();
    loadStyles();
    loadLoras();
    loadRecipes();
    loadPixelProviderCapabilities();

    const styleSelect = $('#pixelStyleProfileSelect');
    if (styleSelect) {
      styleSelect.addEventListener('change', () => compareActiveAssetToStyle());
    }

    const providerSelect = $('#pixelProviderSelect');
    if (providerSelect) {
      providerSelect.addEventListener('change', () => updateProviderCapabilityPanel());
    }

    // Style profile dialog events
    const createStyleBtn = $('#pixelCreateStyleBtn');
    const styleModal = $('#pixelStyleModal');
    const styleModalBackdrop = $('#pixelStyleModalBackdrop');
    const styleCancelBtn = $('#pixelStyleCancelBtn');
    const styleForm = $('#pixelStyleForm');

    if (styleModal) {
      styleModal.classList.add('hidden');
    }

    if (createStyleBtn && styleModal) {
      createStyleBtn.addEventListener('click', () => {
        styleModal.classList.remove('hidden');
        $('#pixelStyleName').value = '';
        $('#pixelStyleOutline').value = 'clean dark outline';
        $('#pixelStyleShading').value = 'cel-shaded';
        $('#pixelStyleCamera').value = 'orthographic front view';
        $('#pixelStylePalette').value = '#1b1b1b, #ffffff';
        $('#pixelStyleLoraSelect').value = '';
        $('#pixelStyleLoraWeight').value = '1.0';
        $('#pixelStyleLoraWeightVal').textContent = '1.0';
      });
    }

    if (styleCancelBtn && styleModal) {
      styleCancelBtn.addEventListener('click', () => {
        styleModal.classList.add('hidden');
      });
    }

    if (styleModalBackdrop && styleModal) {
      styleModalBackdrop.addEventListener('click', () => {
        styleModal.classList.add('hidden');
      });
    }

    if (styleForm) {
      styleForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          name: $('#pixelStyleName').value,
          outline_hint: $('#pixelStyleOutline').value,
          shading_hint: $('#pixelStyleShading').value,
          camera_hint: $('#pixelStyleCamera').value,
          palette: $('#pixelStylePalette').value.split(',').map(s => s.trim()).filter(Boolean),
          lora_name: $('#pixelStyleLoraSelect').value || undefined,
          lora_weight: $('#pixelStyleLoraSelect').value ? parseFloat($('#pixelStyleLoraWeight').value) : undefined
        };

        try {
          const res = await api('/api/pixel-assets/style/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            toast('Style profile saved successfully!');
            styleModal.classList.add('hidden');
            await loadStyles();
            const selectEl = $('#pixelStyleProfileSelect');
            if (selectEl) {
              selectEl.value = res.style.style_id;
            }
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    // Export Modal dialog events (Phase 5)
    const exportModal = $('#pixelExportModal');
    const exportModalBackdrop = $('#pixelExportModalBackdrop');
    const exportCancelBtn = $('#pixelExportCancelBtn');
    const exportForm = $('#pixelExportForm');
    const inspectorExportBtn = $('#inspectorExportBtn');

    if (exportModal) {
      exportModal.classList.add('hidden');
    }

    if (inspectorExportBtn && exportModal) {
      inspectorExportBtn.addEventListener('click', () => {
        if (!activeAsset) return;
        exportModal.classList.remove('hidden');
        const batchId = activeBatch ? activeBatch.batch_id : (activeAsset.batch_id || "");
        $('#pixelExportBatchId').value = batchId;
        $('#pixelExportEngineSelect').value = 'godot';
      });
    }

    if (exportCancelBtn && exportModal) {
      exportCancelBtn.addEventListener('click', () => {
        exportModal.classList.add('hidden');
      });
    }

    if (exportModalBackdrop && exportModal) {
      exportModalBackdrop.addEventListener('click', () => {
        exportModal.classList.add('hidden');
      });
    }

    if (exportForm) {
      exportForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const batchId = $('#pixelExportBatchId').value;
        const engine = $('#pixelExportEngineSelect').value;
        if (!batchId) {
          toast("No active batch to export.");
          return;
        }

        // Trigger file download via location redirect
        const downloadUrl = `/api/pixel-assets/export?batch_id=${encodeURIComponent(batchId)}&engine=${encodeURIComponent(engine)}`;
        window.location.href = downloadUrl;
        
        toast(`Exporting batch spritesheet package for ${engine}...`);
        exportModal.classList.add('hidden');
      });
    }

    // Paint & Edit Canvas Bindings (Phase 7 & 8)
    const inspectorEditBtn = $('#inspectorEditBtn');
    const editorToolbar = $('#pixelEditorToolbar');
    const inpaintToolbar = $('#pixelInpaintToolbar');
    const canvas = $('#pixelEditorCanvas');
    const ctx = canvas.getContext('2d');
    const maskCanvas = $('#pixelMaskCanvas');
    const maskCtx = maskCanvas.getContext('2d');

    const btnPencil = $('#btnEditorPencil');
    const btnEraser = $('#btnEditorEraser');
    const btnBucket = $('#btnEditorBucket');
    const btnPicker = $('#btnEditorPicker');
    const btnLine = $('#btnEditorLine');
    const btnRect = $('#btnEditorRect');
    const btnSelect = $('#btnEditorSelect');
    const btnMove = $('#btnEditorMove');
    const btnMask = $('#btnEditorMask');

    const btnUndo = $('#btnEditorUndo');
    const btnRedo = $('#btnEditorRedo');
    const btnImport = $('#btnEditorImport');
    const editorImportInput = $('#pixelEditorImportInput');
    const btnExport = $('#btnEditorExport');
    const btnVersion = $('#btnEditorVersion');
    const btnCancel = $('#btnEditorCancel');
    const btnSave = $('#btnEditorSave');
    const btnRunInpaint = $('#btnEditorRunInpaint');
    const btnCompareInpaint = $('#btnEditorCompareInpaint');
    const inpaintMaskOpacity = $('#pixelInpaintMaskOpacity');
    const inpaintVariantCount = $('#pixelInpaintVariantCount');

    if (inspectorEditBtn) {
      inspectorEditBtn.addEventListener('click', () => {
        if (!activeAsset) return;

        // Stop animation playing if any
        stopAnimPlayer();

        // Reset compare state and disable buttons
        isEditing = true;
        seamPreviewOn = false;
        if (seamPreviewBtn) {
          seamPreviewBtn.style.display = 'none';
          seamPreviewBtn.textContent = 'Seam Preview: OFF';
        }
        if (gridOverlay) gridOverlay.style.display = gridOn ? 'block' : 'none';

        // Hide skeletal overlays in editing mode
        $('#pixelRigOverlayContainer').style.display = 'none';

        // Swap views
        $('#pixelSpriteImg').style.display = 'none';
        canvas.style.display = 'block';
        maskCanvas.style.display = 'block';
        if (editorToolbar) editorToolbar.style.display = 'flex';

        inspectorEditBtn.disabled = true;
        if (inspectorExportBtn) inspectorExportBtn.disabled = true;
        if ($('#inspectorUseAsStyleBtn')) $('#inspectorUseAsStyleBtn').disabled = true;

        // Draw active asset onto canvas
        const w = activeAsset.resolution[0];
        const h = activeAsset.resolution[1];
        canvas.width = w;
        canvas.height = h;
        maskCanvas.width = w;
        maskCanvas.height = h;
        inpaintCompareSnapshot = null;
        if (inpaintMaskOpacity) {
          maskCanvas.style.opacity = inpaintMaskOpacity.value || '0.8';
        }

        const img = new Image();
        img.onload = function () {
          ctx.clearRect(0, 0, w, h);
          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(img, 0, 0, w, h);
          
          maskCtx.clearRect(0, 0, w, h);

          // Initialize undo stack
          undoStack = [ctx.getImageData(0, 0, w, h)];
          redoStack = [];
          editorSelection = null;
          editorMovedSelection = null;
          editorDragStart = null;
          editorPreviewState = null;
        };
        img.src = '/file/' + activeAsset.outputs.png + '?t=' + Date.now();

        // Highlight active pencil tool
        setEditorTool('pencil');
      });
    }

    function setEditorTool(tool) {
      currentTool = tool;
      [btnPencil, btnEraser, btnBucket, btnPicker, btnLine, btnRect, btnSelect, btnMove, btnMask].forEach(btn => {
        if (btn) btn.classList.remove('active');
      });
      if (tool === 'pencil' && btnPencil) btnPencil.classList.add('active');
      if (tool === 'eraser' && btnEraser) btnEraser.classList.add('active');
      if (tool === 'bucket' && btnBucket) btnBucket.classList.add('active');
      if (tool === 'picker' && btnPicker) btnPicker.classList.add('active');
      if (tool === 'line' && btnLine) btnLine.classList.add('active');
      if (tool === 'rectangle' && btnRect) btnRect.classList.add('active');
      if (tool === 'select' && btnSelect) btnSelect.classList.add('active');
      if (tool === 'move' && btnMove) btnMove.classList.add('active');
      if (tool === 'mask' && btnMask) btnMask.classList.add('active');

      if (tool === 'mask') {
        if (inpaintToolbar) inpaintToolbar.style.display = 'flex';
      } else {
        if (inpaintToolbar) inpaintToolbar.style.display = 'none';
      }
    }

    if (btnPencil) btnPencil.addEventListener('click', () => setEditorTool('pencil'));
    if (btnEraser) btnEraser.addEventListener('click', () => setEditorTool('eraser'));
    if (btnBucket) btnBucket.addEventListener('click', () => setEditorTool('bucket'));
    if (btnPicker) btnPicker.addEventListener('click', () => setEditorTool('picker'));
    if (btnLine) btnLine.addEventListener('click', () => setEditorTool('line'));
    if (btnRect) btnRect.addEventListener('click', () => setEditorTool('rectangle'));
    if (btnSelect) btnSelect.addEventListener('click', () => setEditorTool('select'));
    if (btnMove) btnMove.addEventListener('click', () => setEditorTool('move'));
    if (btnMask) btnMask.addEventListener('click', () => setEditorTool('mask'));

    if (inpaintMaskOpacity) {
      inpaintMaskOpacity.addEventListener('input', () => {
        maskCanvas.style.opacity = inpaintMaskOpacity.value || '0.8';
      });
    }

    // Paint event listeners (bound to top canvas or mask overlay)
    canvas.addEventListener('mousedown', (e) => {
      drawing = true;
      editorDragStart = getCanvasCellFromEvent(e);
      editorPreviewState = ctx.getImageData(0, 0, canvas.width, canvas.height);
      applyPaintTool(e, false);
    });

    canvas.addEventListener('mousemove', (e) => {
      if (drawing) applyPaintTool(e, true);
    });

    const stopDrawing = () => {
      if (drawing) {
        drawing = false;
        // Save current canvas state to undo stack
        undoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
        if (undoStack.length > 50) undoStack.shift();
        redoStack = []; // Clear redo stack on new action
        if (editorMovedSelection) {
          editorSelection = editorMovedSelection;
          editorMovedSelection = null;
        }
        editorDragStart = null;
        editorPreviewState = null;
      }
    };
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseleave', stopDrawing);

    function getCanvasCellFromEvent(e) {
      const rect = canvas.getBoundingClientRect();
      const cellX = Math.floor((e.clientX - rect.left) / rect.width * canvas.width);
      const cellY = Math.floor((e.clientY - rect.top) / rect.height * canvas.height);
      return { x: cellX, y: cellY };
    }

    function applyPaintTool(e, isDrag) {
      const cell = getCanvasCellFromEvent(e);
      const cellX = cell.x;
      const cellY = cell.y;

      if (cellX < 0 || cellX >= canvas.width || cellY < 0 || cellY >= canvas.height) return;

      if (currentTool === 'pencil') {
        ctx.fillStyle = activeColor;
        ctx.fillRect(cellX, cellY, 1, 1);
      } else if (currentTool === 'eraser') {
        ctx.clearRect(cellX, cellY, 1, 1);
      } else if (currentTool === 'bucket') {
        floodFill(cellX, cellY, activeColor);
      } else if (currentTool === 'picker') {
        const pix = ctx.getImageData(cellX, cellY, 1, 1).data;
        if (pix[3] > 0) {
          activeColor = rgbToHex(pix[0], pix[1], pix[2]);
          toast(`Active color picked: ${activeColor}`);
        }
      } else if (currentTool === 'line' && editorDragStart && editorPreviewState) {
        ctx.putImageData(editorPreviewState, 0, 0);
        drawEditorLine(editorDragStart.x, editorDragStart.y, cellX, cellY, activeColor);
      } else if (currentTool === 'rectangle' && editorDragStart && editorPreviewState) {
        ctx.putImageData(editorPreviewState, 0, 0);
        drawEditorRectangle(editorDragStart.x, editorDragStart.y, cellX, cellY, activeColor);
      } else if (currentTool === 'select' && editorDragStart && editorPreviewState) {
        ctx.putImageData(editorPreviewState, 0, 0);
        clearEditorOverlay();
        editorSelection = normalizeRect(editorDragStart.x, editorDragStart.y, cellX, cellY);
        drawEditorSelection(editorSelection);
      } else if (currentTool === 'move' && editorSelection && editorDragStart && editorPreviewState) {
        const dx = cellX - editorDragStart.x;
        const dy = cellY - editorDragStart.y;
        moveEditorSelection(dx, dy);
      } else if (currentTool === 'move' && isDrag) {
        toast('Select a region before using Move.');
      } else if (currentTool === 'mask') {
        const radius = parseInt($('#pixelInpaintBrushSize').value || '2');
        maskCtx.fillStyle = 'rgba(255, 0, 0, 0.5)';
        maskCtx.beginPath();
        maskCtx.arc(cellX, cellY, radius, 0, 2 * Math.PI);
        maskCtx.fill();
      }
    }

    function drawEditorLine(x0, y0, x1, y1, color) {
      let dx = Math.abs(x1 - x0);
      let sx = x0 < x1 ? 1 : -1;
      let dy = -Math.abs(y1 - y0);
      let sy = y0 < y1 ? 1 : -1;
      let err = dx + dy;
      ctx.fillStyle = color;
      while (true) {
        ctx.fillRect(x0, y0, 1, 1);
        if (x0 === x1 && y0 === y1) break;
        const e2 = 2 * err;
        if (e2 >= dy) {
          err += dy;
          x0 += sx;
        }
        if (e2 <= dx) {
          err += dx;
          y0 += sy;
        }
      }
    }

    function drawEditorRectangle(x0, y0, x1, y1, color) {
      const rect = normalizeRect(x0, y0, x1, y1);
      ctx.fillStyle = color;
      ctx.fillRect(rect.x, rect.y, rect.w, 1);
      ctx.fillRect(rect.x, rect.y + rect.h - 1, rect.w, 1);
      ctx.fillRect(rect.x, rect.y, 1, rect.h);
      ctx.fillRect(rect.x + rect.w - 1, rect.y, 1, rect.h);
    }

    function normalizeRect(x0, y0, x1, y1) {
      const x = Math.max(0, Math.min(x0, x1));
      const y = Math.max(0, Math.min(y0, y1));
      const w = Math.min(canvas.width - x, Math.abs(x1 - x0) + 1);
      const h = Math.min(canvas.height - y, Math.abs(y1 - y0) + 1);
      return { x, y, w, h };
    }

    function drawEditorSelection(rect) {
      if (!rect || rect.w < 1 || rect.h < 1) return;
      maskCtx.save();
      maskCtx.strokeStyle = 'rgba(85, 241, 255, 0.85)';
      maskCtx.lineWidth = 1;
      maskCtx.setLineDash([2, 1]);
      maskCtx.strokeRect(rect.x + 0.5, rect.y + 0.5, Math.max(0, rect.w - 1), Math.max(0, rect.h - 1));
      maskCtx.restore();
    }

    function clearEditorOverlay() {
      maskCtx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    }

    function moveEditorSelection(dx, dy) {
      const source = editorPreviewState;
      const rect = editorSelection;
      if (!source || !rect || rect.w < 1 || rect.h < 1) return;
      ctx.putImageData(source, 0, 0);
      const patch = ctx.getImageData(rect.x, rect.y, rect.w, rect.h);
      ctx.clearRect(rect.x, rect.y, rect.w, rect.h);
      const nx = Math.max(0, Math.min(canvas.width - rect.w, rect.x + dx));
      const ny = Math.max(0, Math.min(canvas.height - rect.h, rect.y + dy));
      ctx.putImageData(patch, nx, ny);
      clearEditorOverlay();
      editorMovedSelection = { x: nx, y: ny, w: rect.w, h: rect.h };
      drawEditorSelection(editorMovedSelection);
    }

    // Flood fill algorithm
    function floodFill(startX, startY, fillHex) {
      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imgData.data;
      const targetRGBA = getPixelColor(startX, startY);
      const fillRGBA = hexToRgba(fillHex);

      if (rgbaMatch(targetRGBA, fillRGBA)) return;

      const queue = [[startX, startY]];
      while (queue.length > 0) {
        const [x, y] = queue.shift();
        if (x < 0 || x >= canvas.width || y < 0 || y >= canvas.height) continue;

        const curr = getPixelColor(x, y);
        if (rgbaMatch(curr, targetRGBA)) {
          setPixelColor(x, y, fillRGBA);
          queue.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
        }
      }
      ctx.putImageData(imgData, 0, 0);

      function getPixelColor(x, y) {
        const offset = (y * canvas.width + x) * 4;
        return [data[offset], data[offset + 1], data[offset + 2], data[offset + 3]];
      }
      function setPixelColor(x, y, rgba) {
        const offset = (y * canvas.width + x) * 4;
        data[offset] = rgba[0];
        data[offset + 1] = rgba[1];
        data[offset + 2] = rgba[2];
        data[offset + 3] = rgba[3];
      }
      function rgbaMatch(c1, c2) {
        return c1[0] === c2[0] && c1[1] === c2[1] && c1[2] === c2[2] && c1[3] === c2[3];
      }
    }

    // Helper color conversions
    function hexToRgba(hex) {
      const bigint = parseInt(hex.replace('#', ''), 16);
      return [ (bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255, 255 ];
    }
    function rgbToHex(r, g, b) {
      return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    // Undo / Redo controls
    if (btnUndo) {
      btnUndo.addEventListener('click', () => {
        if (undoStack.length > 1) {
          const current = undoStack.pop();
          redoStack.push(current);
          const previous = undoStack[undoStack.length - 1];
          ctx.putImageData(previous, 0, 0);
        }
      });
    }

    if (btnRedo) {
      btnRedo.addEventListener('click', () => {
        if (redoStack.length > 0) {
          const next = redoStack.pop();
          undoStack.push(next);
          ctx.putImageData(next, 0, 0);
        }
      });
    }

    if (btnCancel) {
      btnCancel.addEventListener('click', () => {
        exitEditorMode();
      });
    }

    if (btnImport && editorImportInput) {
      btnImport.addEventListener('click', () => editorImportInput.click());
      editorImportInput.addEventListener('change', () => {
        const file = editorImportInput.files && editorImportInput.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          const img = new Image();
          img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            undoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
            if (undoStack.length > 50) undoStack.shift();
            redoStack = [];
            toast('Imported PNG into editor canvas.');
          };
          img.src = reader.result;
        };
        reader.readAsDataURL(file);
        editorImportInput.value = '';
      });
    }

    if (btnExport) {
      btnExport.addEventListener('click', () => {
        if (!activeAsset) return;
        const link = document.createElement('a');
        link.href = canvas.toDataURL('image/png');
        link.download = `${activeAsset.asset_id || 'pixel_asset'}_edited.png`;
        link.click();
      });
    }

    if (btnVersion) {
      btnVersion.addEventListener('click', async () => {
        if (!activeAsset) return;
        const label = window.prompt('Version label', 'manual pixel edit');
        if (label === null) return;
        try {
          const res = await api('/api/pixel-assets/version/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              label: label.trim() || 'manual pixel edit'
            })
          });
          if (res.ok) {
            activeAsset = res.asset;
            toast('Version saved.');
            populateInspector(activeAsset);
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    if (btnSave) {
      btnSave.addEventListener('click', async () => {
        if (!activeAsset) return;

        const dataUrl = canvas.toDataURL("image/png");
        try {
          const res = await api('/api/pixel-assets/edit/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              image_data: dataUrl
            })
          });

          if (res.ok) {
            toast("Edits saved successfully!");
            // Update local memory and inspector metrics
            activeAsset.palette = res.asset.palette;
            activeAsset.qa = res.asset.qa;
            
            exitEditorMode();
            selectAsset(activeAsset);
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    async function drawPathToEditorCanvas(relativePath, shouldDraw) {
      if (!relativePath) return;
      await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = function () {
          if (shouldDraw && !shouldDraw()) {
            resolve();
            return;
          }
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.imageSmoothingEnabled = false;
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve();
        };
        img.onerror = reject;
        img.src = '/file/' + relativePath + '?t=' + Date.now();
      });
    }

    function latestInpaintEntry() {
      if (!activeAsset || !Array.isArray(activeAsset.inpaint_history) || activeAsset.inpaint_history.length === 0) {
        return null;
      }
      return activeAsset.inpaint_history[activeAsset.inpaint_history.length - 1];
    }

    if (btnCompareInpaint) {
      const showBefore = async () => {
        const latest = latestInpaintEntry();
        if (!latest || !latest.original_path) {
          toast('No pre-inpaint image has been saved for this asset yet.');
          return;
        }
        inpaintCompareSnapshot = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const token = ++inpaintCompareToken;
        btnCompareInpaint.classList.add('active');
        await drawPathToEditorCanvas(latest.original_path, () => token === inpaintCompareToken && Boolean(inpaintCompareSnapshot));
      };
      const restoreAfter = () => {
        inpaintCompareToken += 1;
        if (inpaintCompareSnapshot) {
          ctx.putImageData(inpaintCompareSnapshot, 0, 0);
          inpaintCompareSnapshot = null;
        }
        btnCompareInpaint.classList.remove('active');
      };
      btnCompareInpaint.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        showBefore().catch(err => showPixelFailure(err.message));
      });
      btnCompareInpaint.addEventListener('pointerup', restoreAfter);
      btnCompareInpaint.addEventListener('pointerleave', restoreAfter);
      btnCompareInpaint.addEventListener('blur', restoreAfter);
    }

    // Run AI inpaint trigger (Phase 8)
    if (btnRunInpaint) {
      btnRunInpaint.addEventListener('click', async () => {
        if (!activeAsset) return;

        const promptVal = $('#pixelInpaintPrompt').value;
        if (!promptVal) {
          toast("Please enter an inpaint prompt description first.");
          return;
        }

        const dataUrl = canvas.toDataURL("image/png");
        const maskUrl = maskCanvas.toDataURL("image/png");
        const variantCountVal = Math.max(1, Math.min(6, parseInt((inpaintVariantCount && inpaintVariantCount.value) || '1', 10) || 1));

        toast("Running AI Edit inpainting...");

        try {
          const providerPlan = await planPixelProviderWorkflow('inpaint');
          if (providerPlan.status === 'missing_key') {
            toast(`Using local fallback: ${providerPlan.action}`);
          } else if (providerPlan.status === 'provider_capable_not_wired') {
            toast('Provider supports masked edits, but this route is using local fallback until its adapter is wired.');
          } else if (providerPlan.status === 'unsupported') {
            toast('Provider does not support masked edits here. Using local fallback.');
          }

          const res = await api('/api/pixel-assets/inpaint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              image_data: dataUrl,
              mask_data: maskUrl,
              prompt: promptVal,
              provider: providerPlan.provider,
              fallback_provider: providerPlan.fallback_provider,
              variant_count: variantCountVal,
              mock: providerPlan.mock_recommended
            })
          });

          if (res.ok) {
            toast("AI Inpainting completed!");
            activeAsset = res.asset || activeAsset;
            
            // Draw returned result onto canvas
            const img = new Image();
            img.onload = function () {
              ctx.clearRect(0, 0, canvas.width, canvas.height);
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
              
              // Push to undo stack
              undoStack.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
              redoStack = [];
              
              // Clear mask canvas
              maskCtx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
              $('#pixelInpaintPrompt').value = '';
              inpaintCompareSnapshot = null;
            };
            img.src = '/file/' + res.asset.outputs.png + '?t=' + Date.now();
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    // Bind Animate Sprite Action (Phase 9)
    const animSpriteBtn = $('#pixelAnimateSpriteBtn');
    const playPauseBtn = $('#btnAnimPlayPause');

    if (animSpriteBtn) {
      animSpriteBtn.addEventListener('click', async () => {
        if (!activeAsset) {
          toast("Please select a base sprite from the gallery first.");
          return;
        }

        const actionType = $('#pixelAnimationTypeSelect').value;
        const frameCount = parseInt($('#pixelAnimationFrameCount').value || '4');
        const fps = parseInt($('#pixelAnimationFps').value || '8');

        toast("Generating frame-by-frame animation...");

        try {
          const res = await api('/api/pixel-assets/animate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              action_type: actionType,
              frame_count: frameCount,
              fps: fps,
              mock: true
            })
          });

          if (res.ok) {
            toast("Animation frames strip compiled!");
            activeAnimation = res.manifest;
            activeBatch = res.manifest; // enable releasing the spritesheet package

            // Show play toggles and QA rows
            $('#pixelAnimationPlayToggleRow').style.display = 'flex';
            $('#pixelSheetViewToggleRow').style.display = 'flex';
            $('#pixelTransferCompareRow').style.display = 'none';
            currentViewMode = 'single'; // default to single frame loop player
            
            const btnShowSheet = $('#btnPreviewShowSheet');
            const btnShowSingle = $('#btnPreviewShowSingle');
            if (btnShowSheet) btnShowSheet.classList.remove('active');
            if (btnShowSingle) btnShowSingle.classList.add('active');

            // Force play loop
            currentFrameIdx = 0;
            startAnimPlayer();
            populateAnimationQA(res.manifest);
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    // Bind Animation Transfer Action (Phase 10)
    const transferBtn = $('#pixelTransferBtn');
    const btnShowTransferred = $('#btnPreviewShowTransferred');
    const btnShowSource = $('#btnPreviewShowSource');

    if (transferBtn) {
      transferBtn.addEventListener('click', async () => {
        const sourcePath = $('#pixelTransferSourceSheet').value;
        const rows = parseInt($('#pixelTransferRows').value || '1');
        const cols = parseInt($('#pixelTransferCols').value || '4');
        const promptVal = $('#pixelTransferPrompt').value;

        if (!sourcePath) {
          toast("Please specify a source spritesheet file path first.");
          return;
        }

        toast("Running pose animation transfer...");

        try {
          const res = await api('/api/pixel-assets/animation-transfer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source_sheet_path: sourcePath,
              rows: rows,
              cols: cols,
              prompt: promptVal,
              mock: true
            })
          });

          if (res.ok) {
            toast("Animation transferred successfully!");
            activeAnimation = res.manifest;
            activeBatch = res.manifest;

            $('#pixelAnimationPlayToggleRow').style.display = 'flex';
            $('#pixelTransferCompareRow').style.display = 'flex';
            $('#pixelSheetViewToggleRow').style.display = 'none';

            currentCompareMode = 'transferred';
            currentViewMode = 'single';

            if (btnShowTransferred) btnShowTransferred.classList.add('active');
            if (btnShowSource) btnShowSource.classList.remove('active');

            currentFrameIdx = 0;
            startAnimPlayer();
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    if (btnShowTransferred && btnShowSource) {
      btnShowTransferred.addEventListener('click', () => {
        btnShowTransferred.classList.add('active');
        btnShowSource.classList.remove('active');
        currentCompareMode = 'transferred';
        renderAnimFrame();
      });
      btnShowSource.addEventListener('click', () => {
        btnShowSource.classList.add('active');
        btnShowTransferred.classList.remove('active');
        currentCompareMode = 'source';
        renderAnimFrame();
      });
    }

    // Bind Skeleton Rigging timeline toggles & renderers (Phase 11)
    const btnRigKey0 = $('#btnRigKeyframe0');
    const btnRigKey1 = $('#btnRigKeyframe1');
    const sliderHead = $('#pixelRigHeadAngle');
    const sliderLeft = $('#pixelRigArmLeftAngle');
    const sliderRight = $('#pixelRigArmRightAngle');
    const rigRenderBtn = $('#pixelRigRenderBtn');

    if (btnRigKey0 && btnRigKey1) {
      btnRigKey0.addEventListener('click', () => {
        // Save current angles
        rigKeyframes[activeRigKeyframe].angles.head = parseInt(sliderHead.value);
        rigKeyframes[activeRigKeyframe].angles.arm_left = parseInt(sliderLeft.value);
        rigKeyframes[activeRigKeyframe].angles.arm_right = parseInt(sliderRight.value);

        activeRigKeyframe = 0;
        btnRigKey0.classList.add('active');
        btnRigKey1.classList.remove('active');

        // Load Pose A angles
        sliderHead.value = rigKeyframes[0].angles.head;
        sliderLeft.value = rigKeyframes[0].angles.arm_left;
        sliderRight.value = rigKeyframes[0].angles.arm_right;

        $('#pixelRigHeadAngleVal').textContent = sliderHead.value + '°';
        $('#pixelRigArmLeftAngleVal').textContent = sliderLeft.value + '°';
        $('#pixelRigArmRightAngleVal').textContent = sliderRight.value + '°';
        syncRigOverlayRotations();
      });

      btnRigKey1.addEventListener('click', () => {
        // Save current angles
        rigKeyframes[activeRigKeyframe].angles.head = parseInt(sliderHead.value);
        rigKeyframes[activeRigKeyframe].angles.arm_left = parseInt(sliderLeft.value);
        rigKeyframes[activeRigKeyframe].angles.arm_right = parseInt(sliderRight.value);

        activeRigKeyframe = 1;
        btnRigKey1.classList.add('active');
        btnRigKey0.classList.remove('active');

        // Load Pose B angles
        sliderHead.value = rigKeyframes[1].angles.head;
        sliderLeft.value = rigKeyframes[1].angles.arm_left;
        sliderRight.value = rigKeyframes[1].angles.arm_right;

        $('#pixelRigHeadAngleVal').textContent = sliderHead.value + '°';
        $('#pixelRigArmLeftAngleVal').textContent = sliderLeft.value + '°';
        $('#pixelRigArmRightAngleVal').textContent = sliderRight.value + '°';
        syncRigOverlayRotations();
      });
    }

    [sliderHead, sliderLeft, sliderRight].forEach(slider => {
      if (slider) {
        slider.addEventListener('input', () => {
          rigKeyframes[activeRigKeyframe].angles.head = parseInt(sliderHead.value);
          rigKeyframes[activeRigKeyframe].angles.arm_left = parseInt(sliderLeft.value);
          rigKeyframes[activeRigKeyframe].angles.arm_right = parseInt(sliderRight.value);
          syncRigOverlayRotations();
        });
      }
    });

    function syncRigOverlayRotations() {
      // Apply rotative CSS transforms to overlay handle joints to show responsive feedback!
      const head = $('#handleHead');
      const left = $('#handleArmLeft');
      const right = $('#handleArmRight');

      const angles = rigKeyframes[activeRigKeyframe].angles;
      if (head) head.style.transform = `translate(-50%, -50%) rotate(${angles.head}deg)`;
      if (left) left.style.transform = `translate(-50%, -50%) rotate(${angles.arm_left}deg)`;
      if (right) right.style.transform = `translate(-50%, -50%) rotate(${angles.arm_right}deg)`;
    }

    if (rigRenderBtn) {
      rigRenderBtn.addEventListener('click', async () => {
        if (!activeAsset) {
          toast("Please select a character sprite from the gallery first.");
          return;
        }

        // Save current angles
        rigKeyframes[activeRigKeyframe].angles.head = parseInt(sliderHead.value);
        rigKeyframes[activeRigKeyframe].angles.arm_left = parseInt(sliderLeft.value);
        rigKeyframes[activeRigKeyframe].angles.arm_right = parseInt(sliderRight.value);

        toast("Rendering skeletal bone rigging animation...");

        try {
          const res = await api('/api/pixel-assets/rig/render', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              keyframes: rigKeyframes,
              frame_count: 4,
              mock: true
            })
          });

          if (res.ok) {
            toast("Rig animation rendered successfully!");
            activeAnimation = res.manifest;
            activeBatch = res.manifest;

            $('#pixelAnimationPlayToggleRow').style.display = 'flex';
            $('#pixelSheetViewToggleRow').style.display = 'flex';
            $('#pixelTransferCompareRow').style.display = 'none';

            currentViewMode = 'single';
            const btnShowSheet = $('#btnPreviewShowSheet');
            const btnShowSingle = $('#btnPreviewShowSingle');
            if (btnShowSheet) btnShowSheet.classList.remove('active');
            if (btnShowSingle) btnShowSingle.classList.add('active');

            currentFrameIdx = 0;
            startAnimPlayer();
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    // Bind Pack Builder generate & export triggers (Phase 12)
    const packGenerateBtn = $('#pixelPackGenerateBtn');
    const exportPackBtn = $('#inspectorExportPackBtn');
    const recipeSelect = $('#pixelPackRecipeSelect');
    const recipeSaveBtn = $('#pixelRecipeSaveBtn');
    const recipeExportBtn = $('#pixelRecipeExportBtn');
    const recipeImportBtn = $('#pixelRecipeImportBtn');
    const recipeImportInput = $('#pixelRecipeImportInput');

    if (recipeSelect) {
      recipeSelect.addEventListener('change', renderSelectedRecipeMeta);
    }

    if (recipeSaveBtn) {
      recipeSaveBtn.addEventListener('click', async () => {
        const payload = buildRecipeFromCurrentSettings();
        try {
          const res = await api('/api/pixel-assets/recipes/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (res.ok) {
            toast('Pixel Studio recipe saved.');
            await loadRecipes();
            const select = $('#pixelPackRecipeSelect');
            if (select) {
              select.value = res.recipe.recipe_id;
              renderSelectedRecipeMeta();
            }
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    if (recipeExportBtn) {
      recipeExportBtn.addEventListener('click', () => {
        const recipeId = $('#pixelPackRecipeSelect').value;
        if (!recipeId) {
          toast('Choose a recipe first.');
          return;
        }
        window.location.href = `/api/pixel-assets/recipes/export?recipe_id=${encodeURIComponent(recipeId)}`;
      });
    }

    if (recipeImportBtn && recipeImportInput) {
      recipeImportBtn.addEventListener('click', () => recipeImportInput.click());
      recipeImportInput.addEventListener('change', () => {
        const file = recipeImportInput.files && recipeImportInput.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async () => {
          try {
            const recipe = JSON.parse(reader.result);
            const res = await api('/api/pixel-assets/recipes/import', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(recipe)
            });
            if (res.ok) {
              toast('Recipe imported.');
              await loadRecipes();
              if (recipeSelect && res.recipe && res.recipe.recipe_id) {
                recipeSelect.value = res.recipe.recipe_id;
                renderSelectedRecipeMeta();
              }
            } else {
              showPixelFailure(res.message || 'Recipe import failed.');
            }
          } catch (err) {
            showPixelFailure(`Recipe import failed: ${err.message}`);
          } finally {
            recipeImportInput.value = '';
          }
        };
        reader.readAsText(file);
      });
    }

    if (packGenerateBtn) {
      packGenerateBtn.addEventListener('click', async () => {
        const recipeType = $('#pixelPackRecipeSelect').value;
        const styleProfileId = $('#pixelStyleProfileSelect').value;

        toast("Generating complete cohesive game asset pack batch...");

        try {
          const res = await api('/api/pixel-assets/pack/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              recipe_type: recipeType,
              style_profile_id: styleProfileId,
              mock: true
            })
          });

          if (res.ok) {
            toast("Cohesive game asset pack generated!");
            activePack = res.manifest;
            activeBatch = null;

            // Display and enable export pack button
            if (exportPackBtn) {
              exportPackBtn.style.display = 'block';
              exportPackBtn.disabled = false;
            }

            // Load the assets list into the gallery
            renderGallery(res.manifest.assets);
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    if (exportPackBtn) {
      exportPackBtn.addEventListener('click', () => {
        if (!activePack) return;
        toast("Exporting cohesive asset pack release ZIP...");
        window.location.href = `/api/pixel-assets/pack/export?pack_id=${activePack.pack_id}`;
      });
    }

    const useAsStyleBtn = $('#inspectorUseAsStyleBtn');
    if (useAsStyleBtn) {
      useAsStyleBtn.addEventListener('click', async () => {
        if (!activeAsset) {
          toast('Select an asset first.');
          return;
        }
        try {
          const res = await api('/api/pixel-assets/style/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              name: `${activeAsset.prompt || activeAsset.asset_type} style`,
              max_colors: activeAsset.palette?.max_colors || 24
            })
          });
          if (res.ok) {
            toast('Style profile extracted from selected asset.');
            await loadStyles();
            const select = $('#pixelStyleProfileSelect');
            if (select) select.value = res.style.style_id;
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    const generateLikeBtn = $('#inspectorGenerateLikeBtn');
    if (generateLikeBtn) {
      generateLikeBtn.addEventListener('click', () => {
        if (!activeAsset) {
          toast('Select an asset first.');
          return;
        }
        const promptEl = $('#pixelPrompt');
        if (promptEl) promptEl.value = `${activeAsset.prompt || activeAsset.asset_type}, matching selected asset palette and silhouette`;
        if ($('#pixelActiveMode')) $('#pixelActiveMode').value = activeAsset.asset_type || $('#pixelActiveMode').value;
        if ($('#pixelBatchCount')) $('#pixelBatchCount').value = '4';
        toast('Prompt seeded from selected asset.');
      });
    }

    const reskinBtn = $('#inspectorReskinBtn');
    const reskinModal = $('#pixelReskinModal');
    const reskinBackdrop = $('#pixelReskinModalBackdrop');
    const reskinCancelBtn = $('#pixelReskinCancelBtn');
    const reskinForm = $('#pixelReskinForm');
    const reskinGrid = $('#pixelReskinVariantGrid');
    if (reskinBtn && reskinModal) {
      reskinBtn.addEventListener('click', () => {
        if (!activeAsset) {
          toast('Select an asset first.');
          return;
        }
        reskinModal.classList.remove('hidden');
        const promptInput = $('#pixelReskinPrompt');
        if (promptInput && !promptInput.value) promptInput.value = 'ice blue variant';
      });
    }
    const closeReskinModal = () => {
      if (reskinModal) reskinModal.classList.add('hidden');
    };
    if (reskinBackdrop) reskinBackdrop.addEventListener('click', closeReskinModal);
    if (reskinCancelBtn) reskinCancelBtn.addEventListener('click', closeReskinModal);
    if (reskinForm) {
      reskinForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeAsset) return;
        const prompt = $('#pixelReskinPrompt')?.value?.trim() || '';
        const count = parseInt($('#pixelReskinCount')?.value || '6', 10);
        if (reskinGrid) {
          reskinGrid.innerHTML = '<div style="font-size: 12px; color: var(--muted); grid-column: 1 / -1;">Generating reskins...</div>';
        }
        try {
          const res = await api('/api/pixel-assets/reskin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              prompt,
              count,
              mock: true
            })
          });
          if (res.ok) {
            renderReskinVariants(res.variants || []);
            toast('Reskin variants generated.');
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    const cleanupBtn = $('#inspectorCleanupBtn');
    if (cleanupBtn) {
      cleanupBtn.addEventListener('click', cleanupSelectedAsset);
    }

    const matchStyleBtn = $('#inspectorMatchStyleBtn');
    if (matchStyleBtn) {
      matchStyleBtn.addEventListener('click', async () => {
        if (!activeAsset) {
          toast('Select an asset first.');
          return;
        }
        const styleId = $('#pixelStyleProfileSelect')?.value || '';
        if (!styleId) {
          toast('Choose a style profile first.');
          return;
        }
        await compareActiveAssetToStyle(true);
        const promptEl = $('#pixelPrompt');
        if (promptEl) promptEl.value = `${activeAsset.prompt || activeAsset.asset_type}, match selected project style profile`;
      });
    }

    const applyPartBtn = $('#inspectorApplyPartBtn');
    const partModal = $('#pixelPartApplyModal');
    const partBackdrop = $('#pixelPartApplyModalBackdrop');
    const partCancelBtn = $('#pixelPartApplyCancelBtn');
    const partForm = $('#pixelPartApplyForm');
    const partGrid = $('#pixelPartVariantGrid');
    if (applyPartBtn && partModal) {
      applyPartBtn.addEventListener('click', () => {
        if (!activeAsset) {
          toast('Select a character or sprite first.');
          return;
        }
        partModal.classList.remove('hidden');
        const promptInput = $('#pixelPartPrompt');
        if (promptInput && !promptInput.value) promptInput.value = 'iron chest armor';
      });
    }
    const closePartModal = () => {
      if (partModal) partModal.classList.add('hidden');
    };
    if (partBackdrop) partBackdrop.addEventListener('click', closePartModal);
    if (partCancelBtn) partCancelBtn.addEventListener('click', closePartModal);
    if (partForm) {
      partForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeAsset) return;
        const prompt = $('#pixelPartPrompt')?.value?.trim() || '';
        const count = parseInt($('#pixelPartVariantCount')?.value || '3', 10);
        const file = $('#pixelPartImageInput')?.files?.[0] || null;
        let imageData = '';
        if (file) imageData = await readFileDataUrl(file);
        if (partGrid) {
          partGrid.innerHTML = '<div style="font-size: 12px; color: var(--muted); grid-column: 1 / -1;">Generating variants...</div>';
        }
        try {
          const res = await api('/api/pixel-assets/part/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              part_prompt: prompt,
              part_image_data: imageData,
              count,
              mock: true
            })
          });
          if (res.ok) {
            renderPartVariants(res.variants || []);
            toast('Part variants generated.');
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
    }

    if (playPauseBtn) {
      playPauseBtn.addEventListener('click', () => {
        if (!activeAnimation) return;
        if (isPlaying) {
          stopAnimPlayer();
        } else {
          startAnimPlayer();
        }
      });
    }

    function startAnimPlayer() {
      if (!activeAnimation) return;
      clearInterval(animInterval);
      isPlaying = true;
      if (playPauseBtn) playPauseBtn.textContent = "⏸️ Pause";

      animInterval = setInterval(() => {
        currentFrameIdx = (currentFrameIdx + 1) % activeAnimation.frame_count;
        renderAnimFrame();
      }, 1000 / (activeAnimation.fps || 8));
    }

    function stopAnimPlayer() {
      isPlaying = false;
      clearInterval(animInterval);
      if (playPauseBtn) playPauseBtn.textContent = "▶️ Play";
    }

    function renderAnimFrame() {
      if (!activeAnimation) return;

      const spriteImg = $('#pixelSpriteImg');
      const spriteContainer = $('#pixelSpriteContainer');
      const w = activeAnimation.resolution[0];
      const h = activeAnimation.resolution[1];
      const cols = activeAnimation.cols || activeAnimation.frame_count;

      $('#txtAnimFrameCounter').textContent = `F: ${currentFrameIdx + 1}/${activeAnimation.frame_count}`;

      if (currentViewMode === 'sheet') {
        // Show whole spritesheet
        spriteImg.style.display = 'block';
        spriteContainer.style.backgroundImage = 'none';
        spriteContainer.style.width = '128px';
        spriteContainer.style.height = '128px';
        spriteImg.src = '/file/' + activeAnimation.outputs.sheet + '?t=' + Date.now();
      } else {
        // Live loop player (crop single active frame)
        spriteImg.style.display = 'none';
        spriteContainer.style.width = `${w}px`;
        spriteContainer.style.height = `${h}px`;
        
        let path = activeAnimation.outputs.sheet;
        if (currentCompareMode === 'source' && activeAnimation.source_sheet) {
          path = activeAnimation.source_sheet;
        }

        spriteContainer.style.backgroundImage = `url('/file/${path}?t=${Date.now()}')`;
        spriteContainer.style.backgroundRepeat = 'no-repeat';
        
        // Scale background image size to cover all frames horizontally & vertically
        const rows = activeAnimation.rows || 1;
        spriteContainer.style.backgroundSize = `${w * cols}px ${h * rows}px`;
        
        const cellX = currentFrameIdx % cols;
        const cellY = Math.floor(currentFrameIdx / cols);
        spriteContainer.style.backgroundPosition = `-${cellX * w}px -${cellY * h}px`;
      }
    }

    function populateAnimationQA(manifest) {
      const animQARows = $('#qaAnimationRows');
      if (animQARows && manifest.qa) {
        animQARows.style.display = 'flex';
        $('#qaBboxJitter').textContent = manifest.qa.bbox_jitter.toFixed(2);
        $('#qaPaletteDrift').textContent = `${(manifest.qa.palette_drift * 100).toFixed(0)}%`;
        $('#qaLoopContinuity').textContent = `${(manifest.qa.loop_continuity * 100).toFixed(0)}%`;
      }
    }

    function exitEditorMode() {
      isEditing = false;
      canvas.style.display = 'none';
      maskCanvas.style.display = 'none';
      $('#pixelSpriteImg').style.display = 'block';
      if (editorToolbar) editorToolbar.style.display = 'none';
      if (inpaintToolbar) inpaintToolbar.style.display = 'none';

      if (inspectorEditBtn) inspectorEditBtn.disabled = false;
      if (inspectorExportBtn) inspectorExportBtn.disabled = false;
      if ($('#inspectorUseAsStyleBtn')) $('#inspectorUseAsStyleBtn').disabled = false;
      
      const seamBtn = $('#pixelSeamPreviewBtn');
      if (seamBtn && activeAsset && activeAsset.asset_type === 'tileset') {
        seamBtn.style.display = 'block';
      }

      if (activeAsset && activeAsset.asset_type === 'characters') {
        $('#pixelRigOverlayContainer').style.display = 'block';
      }
    }

    // Action buttons
    const dryRunBtn = $('#pixelDryRunBtn');
    const generateBtn = $('#pixelGenerateBtn');
    const planDismissBtn = $('#pixelClosePlanBtn');
    const normalizeBtn = $('#pixelNormalizeTriggerBtn');

    if (dryRunBtn) {
      dryRunBtn.addEventListener('click', () => runGenerationFlow(true));
    }
    if (generateBtn) {
      generateBtn.addEventListener('click', () => runGenerationFlow(false));
    }
    if (planDismissBtn) {
      planDismissBtn.addEventListener('click', () => {
        const planPanel = $('#pixelPlanPanel');
        if (planPanel) planPanel.style.display = 'none';
      });
    }
    if (normalizeBtn) {
      normalizeBtn.addEventListener('click', triggerReNormalization);
    }

    // Before/After comparison toggles
    const btnNormalized = $('#btnPreviewShowNormalized');
    const btnRaw = $('#btnPreviewShowRaw');
    if (btnNormalized && btnRaw) {
      btnNormalized.addEventListener('click', () => {
        btnNormalized.classList.add('active');
        btnRaw.classList.remove('active');
        currentCompareMode = 'normalized';
        syncComparePreview();
      });
      btnRaw.addEventListener('click', () => {
        btnRaw.classList.add('active');
        btnNormalized.classList.add('active');
        currentCompareMode = 'raw';
        syncComparePreview();
      });
    }

    // View Sheet / Active Direction toggles (Phase 3)
    const btnShowSheet = $('#btnPreviewShowSheet');
    const btnShowSingle = $('#btnPreviewShowSingle');
    if (btnShowSheet && btnShowSingle) {
      btnShowSheet.addEventListener('click', () => {
        btnShowSheet.classList.add('active');
        btnShowSingle.classList.remove('active');
        currentViewMode = 'sheet';
        // Clear active loop interval if showing full sheet
        if (activeAnimation) stopAnimPlayer();
        syncComparePreview();
        if (activeAnimation) renderAnimFrame();
      });
      btnShowSingle.addEventListener('click', () => {
        btnShowSingle.classList.add('active');
        btnShowSheet.classList.remove('active');
        currentViewMode = 'single';
        syncComparePreview();
        if (activeAnimation) {
          startAnimPlayer();
        }
      });
    }
  }

  async function loadStyles() {
    const selectEl = $('#pixelStyleProfileSelect');
    if (!selectEl) return;

    try {
      const res = await api('/api/pixel-assets/style/list');
      if (res.ok && res.styles) {
        styleProfiles = res.styles;
        selectEl.innerHTML = '<option value="">-- Select Profile --</option>';
        res.styles.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.style_id;
          opt.textContent = p.name;
          selectEl.appendChild(opt);
        });
      }
    } catch (err) {
      console.error('Error loading styles:', err);
    }
  }

  async function loadModeConfigs() {
    try {
      const res = await api('/api/pixel-assets/modes');
      if (res.ok && res.mode_configs) {
        pixelModeConfigs = res.mode_configs;
        renderModeOptions($('#pixelActiveMode')?.value || 'characters');
      }
    } catch (err) {
      console.error('Error loading mode configs:', err);
    }
  }

  function renderModeOptions(mode) {
    const container = $('#pixelModeOptionsContainer');
    if (!container) return;

    const config = pixelModeConfigs[mode] || {};
    const controls = config.controls || {};
    container.innerHTML = '';

    Object.keys(controls).forEach(controlId => {
      const label = document.createElement('label');
      label.textContent = controlId.replaceAll('_', ' ');
      label.style.fontSize = '11px';
      label.style.textTransform = 'uppercase';
      label.style.color = 'var(--muted)';

      const select = document.createElement('select');
      select.dataset.pixelModeOption = controlId;
      select.style.width = '100%';
      select.style.marginTop = '4px';

      controls[controlId].forEach(value => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        select.appendChild(opt);
      });

      label.appendChild(select);
      container.appendChild(label);
    });

    if (!Object.keys(controls).length) {
      container.innerHTML = '<div style="grid-column: 1 / -1; color: var(--muted); font-size: 11px;">No extra controls for this asset type.</div>';
    }
  }

  function collectModeOptions() {
    const out = {};
    $$('[data-pixel-mode-option]').forEach(select => {
      out[select.dataset.pixelModeOption] = select.value;
    });
    return out;
  }

  function applyPixelWorkflow(workflowId) {
    const modeByWorkflow = {
      first_asset: 'weapons',
      first_tileset: 'tilesets',
      first_animation: 'characters',
      first_pack: 'characters'
    };
    const mode = modeByWorkflow[workflowId] || 'characters';
    const tab = $(`[data-mode-tab="${mode}"]`);
    if (tab) tab.click();

    const prompts = {
      first_asset: 'iron sword pickup icon',
      first_tileset: 'mossy dungeon stone floor',
      first_animation: 'forest ranger adventurer',
      first_pack: 'cozy rpg starter assets'
    };
    const promptEl = $('#pixelPrompt');
    if (promptEl) promptEl.value = prompts[workflowId] || prompts.first_asset;

    if ($('#pixelResolutionSelect')) {
      $('#pixelResolutionSelect').value = workflowId === 'first_asset' ? '16x16' : '32x32';
    }
    if ($('#pixelPaletteSizeSelect')) $('#pixelPaletteSizeSelect').value = '16';
    if ($('#pixelBatchCount')) $('#pixelBatchCount').value = workflowId === 'first_pack' ? '1' : '4';
    if ($('#pixelDirectionsSelect')) $('#pixelDirectionsSelect').value = workflowId === 'first_animation' ? '4' : '1';

    if (workflowId === 'first_pack') {
      const recipe = $('#pixelPackRecipeSelect');
      if (recipe) {
        recipe.value = 'rpg_starter';
        renderSelectedRecipeMeta();
      }
    }

    toast('Pixel Studio workflow ready.');
  }

  async function showPixelFailure(message) {
    const text = message || 'Pixel Studio request failed.';
    toast(text);
    try {
      const res = await api('/api/pixel-assets/failure/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      if (res.ok && res.explainer) {
        renderPixelFailure(res.explainer);
      }
    } catch (err) {
      console.error('Error explaining Pixel Studio failure:', err);
    }
  }

  function renderPixelFailure(explainer) {
    const panel = $('#pixelFailurePanel');
    if (!panel) return;
    $('#pixelFailureTitle').textContent = explainer.title || 'Pixel Studio issue';
    $('#pixelFailureWhat').textContent = explainer.what_happened || '';
    $('#pixelFailureFix').textContent = explainer.fix || '';
    panel.style.display = 'block';
  }

  async function loadRecipes() {
    const selectEl = $('#pixelPackRecipeSelect');
    if (!selectEl) return;

    try {
      const res = await api('/api/pixel-assets/recipes');
      if (res.ok && res.recipes) {
        const current = selectEl.value;
        pixelRecipes = res.recipes;
        selectEl.innerHTML = '';
        res.recipes.forEach(recipe => {
          const opt = document.createElement('option');
          opt.value = recipe.recipe_id;
          const count = (recipe.items || []).reduce((total, item) => total + (item.count || 1), 0);
          opt.textContent = `${recipe.name} (${count} assets)`;
          selectEl.appendChild(opt);
        });
        if (current && res.recipes.some(recipe => recipe.recipe_id === current)) {
          selectEl.value = current;
        }
        renderSelectedRecipeMeta();
      }
    } catch (err) {
      console.error('Error loading recipes:', err);
    }
  }

  function renderSelectedRecipeMeta() {
    const meta = $('#pixelRecipeMeta');
    const selectEl = $('#pixelPackRecipeSelect');
    if (!meta || !selectEl) return;

    const recipe = pixelRecipes.find(item => item.recipe_id === selectEl.value);
    if (!recipe) {
      meta.textContent = 'Recipe details load here.';
      return;
    }

    const jobs = (recipe.items || []).map(item => `${item.count || 1}x ${item.type}: ${item.prompt}`).join(' | ');
    meta.textContent = `${recipe.description || recipe.name} ${jobs}`;
  }

  function buildRecipeFromCurrentSettings() {
    const mode = $('#pixelActiveMode').value;
    const prompt = $('#pixelPrompt').value || $('#pixelPrompt').placeholder || 'pixel art asset';
    const resolution = $('#pixelResolutionSelect').value;
    const count = Math.max(1, parseInt($('#pixelBatchCount').value || '1'));
    const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);

    return {
      schema: 'spriteforge.pixel_recipe.v1',
      recipe_id: `recipe_${mode}_${timestamp}`,
      name: `${mode.replace('_', ' ')} recipe`,
      description: 'Saved from the current Pixel Studio generation settings.',
      tags: [mode, 'custom'],
      items: [{
        type: mode,
        prompt,
        resolution,
        count
      }]
    };
  }

  async function loadLoras() {
    const selectEl = $('#pixelStyleLoraSelect');
    if (!selectEl) return;

    try {
      const res = await api('/api/pixel-assets/loras');
      if (res.ok && res.loras) {
        selectEl.innerHTML = '<option value="">-- No LoRA --</option>';
        res.loras.forEach(l => {
          const opt = document.createElement('option');
          opt.value = l.lora_id;
          opt.textContent = l.name;
          selectEl.appendChild(opt);
        });
      }
    } catch (err) {
      console.error('Error loading LoRAs:', err);
    }
  }

  async function loadPixelProviderCapabilities() {
    try {
      const res = await api('/api/pixel-assets/providers/capabilities');
      if (!res.ok) {
        throw new Error(res.message || 'Could not load provider capabilities.');
      }
      pixelProviderCapabilities = res.providers || {};
      hydrateProviderSelectOptions();
      updateProviderCapabilityPanel();
    } catch (err) {
      const messageEl = $('#pixelProviderCapabilityMessage');
      if (messageEl) messageEl.textContent = err.message || 'Provider capability check failed.';
    }
  }

  function hydrateProviderSelectOptions() {
    const selectEl = $('#pixelProviderSelect');
    if (!selectEl || !pixelProviderCapabilities) return;
    const current = selectEl.value || 'local_mock';
    const ordered = ['local_mock', 'comfyui', 'openai', 'gemini', 'huggingface', 'anthropic', 'moonshot', 'glm', 'deepseek', 'grok'];
    selectEl.innerHTML = '';
    ordered.filter(provider => pixelProviderCapabilities[provider]).forEach(provider => {
      const row = pixelProviderCapabilities[provider];
      const opt = document.createElement('option');
      opt.value = provider;
      opt.textContent = row.label || provider;
      selectEl.appendChild(opt);
    });
    if (pixelProviderCapabilities[current]) {
      selectEl.value = current;
    } else {
      selectEl.value = pixelProviderCapabilities.openai ? 'openai' : Object.keys(pixelProviderCapabilities)[0] || '';
    }
  }

  function updateProviderCapabilityPanel() {
    const selectEl = $('#pixelProviderSelect');
    const badgesEl = $('#pixelProviderCapabilityBadges');
    const messageEl = $('#pixelProviderCapabilityMessage');
    if (!selectEl || !badgesEl || !messageEl) return;
    const provider = selectEl.value || 'local_mock';
    const row = pixelProviderCapabilities[provider];
    activeProviderCapability = row || null;
    badgesEl.innerHTML = '';
    if (!row) {
      messageEl.textContent = 'Provider capability data is not loaded yet.';
      return;
    }

    const caps = row.capabilities || {};
    ['generate', 'edit', 'inpaint', 'prompt_help'].forEach(name => {
      const badge = document.createElement('span');
      const supported = Boolean(caps[name]);
      badge.className = `pixel-provider-capability-badge ${supported ? 'ready' : 'limited'}`;
      badge.textContent = `${supported ? 'yes' : 'no'} ${name.replace('_', ' ')}`;
      badgesEl.appendChild(badge);
    });

    const freeText = row.local ? 'local' : (row.free_tier ? 'free/trial possible' : 'paid/keyed');
    const configuredText = row.configured || row.local ? 'configured' : 'missing key';
    const limitText = row.limits && row.limits.length ? ` ${row.limits[0]}` : '';
    messageEl.textContent = `${row.label || provider}: ${configuredText}, ${freeText}.${limitText}`;
  }

  async function planPixelProviderWorkflow(workflow) {
    const provider = ($('#pixelProviderSelect') && $('#pixelProviderSelect').value) || 'local_mock';
    const res = await api('/api/pixel-assets/providers/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, workflow })
    });
    if (!res.ok) {
      throw new Error(res.message || `Could not plan ${workflow} provider workflow.`);
    }
    return res;
  }

  async function runGenerationFlow(dryRun) {
    const activeMode = $('#pixelActiveMode').value;
    const promptVal = $('#pixelPrompt').value || $('#pixelPrompt').placeholder || "pixel art";
    const negativeVal = $('#pixelNegativePrompt').value;
    const referenceVal = $('#pixelReferenceImage').value;
    const styleProfileId = $('#pixelStyleProfileSelect').value;
    const resolutionVal = $('#pixelResolutionSelect').value;
    const paletteSizeVal = $('#pixelPaletteSizeSelect').value;
    const providerVal = $('#pixelProviderSelect').value;
    const countVal = parseInt($('#pixelBatchCount').value || '4');
    const directionCount = parseInt($('#pixelDirectionsSelect').value || '1');

    // Normalization rules from sidebar
    const cleanAlpha = $('#pixelCleanAlphaToggle').checked;
    const quantizePalette = $('#pixelQuantizeToggle').checked;
    const removeIslands = $('#pixelRemoveIslandsToggle').checked;
    const outline = $('#pixelOutlineSelect').value;

    const payload = {
      asset_type: activeMode,
      prompt: promptVal,
      negative: negativeVal,
      reference_image: referenceVal,
      style_profile_id: styleProfileId,
      mode_options: collectModeOptions(),
      resolution: resolutionVal,
      palette_size: paletteSizeVal,
      provider: providerVal,
      count: directionCount > 1 ? directionCount : countVal,
      dry_run: dryRun,
      // Normalization rules
      clean_alpha: cleanAlpha,
      quantize_palette: quantizePalette,
      remove_islands: removeIslands,
      outline: outline,
      // Fallback flag for quick testing
      mock: true
    };

    // If style profile has associated LoRA, send it directly in payload too
    if (styleProfileId) {
      const activeProfile = styleProfiles.find(p => p.style_id === styleProfileId);
      if (activeProfile && activeProfile.lora_name) {
        payload.lora_name = activeProfile.lora_name;
        payload.lora_weight = activeProfile.lora_weight;
        payload.base_model = activeProfile.base_model;
      }
    }

    try {
      let res;
      if (activeMode === 'tilesets' && !dryRun) {
        // Tileset generation endpoint (Phase 6)
        payload.tileset_type = $('#pixelTilesetTypeSelect').value;
        res = await api('/api/pixel-assets/tileset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else if (directionCount > 1 && !dryRun) {
        // Multi-direction generation API endpoint
        res = await api('/api/pixel-assets/directions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        // Standard generation / plan endpoint
        res = await api('/api/pixel-assets/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (res.ok) {
        if (dryRun) {
          toast('Plan preview compiled successfully.');
          displayPlan(res.plan);
        } else {
          toast('Pixel asset generated successfully!');
          
          if (activeMode === 'tilesets' || directionCount > 1) {
            // Re-bind batch information to each asset for visualizer stitching
            res.assets.forEach(asset => {
              asset.manifest = res.manifest;
            });
            activeBatch = res.manifest;
            renderGallery(res.assets);
          } else {
            activeBatch = null;
            renderGallery(res.assets);
          }
        }
      } else {
        showPixelFailure(res.message);
      }
    } catch (err) {
      showPixelFailure(err.message);
    }
  }

  function displayPlan(plan) {
    const panel = $('#pixelPlanPanel');
    if (!panel) return;

    panel.style.display = 'block';
    $('#pixelPlanPrompt').textContent = plan.expanded_prompt;
    
    // Format payload cleanly including lora_config if present
    $('#pixelPlanPayload').textContent = JSON.stringify(plan.cloud_plan.generation_contract, null, 2);

    const pipelineEl = $('#pixelPlanPipeline');
    if (pipelineEl) {
      pipelineEl.innerHTML = '';
      plan.cloud_plan.processing_steps.forEach(step => {
        const li = document.createElement('li');
        li.innerHTML = `<strong>${step.name}:</strong> ${step.detail}`;
        pipelineEl.appendChild(li);
      });
    }
  }

  function renderGallery(assets) {
    const container = $('#pixelGalleryContainer');
    const emptyState = $('#pixelGalleryEmptyState');
    if (!container) return;

    if (emptyState) emptyState.remove();
    container.innerHTML = '';

    assets.forEach((asset, idx) => {
      const card = document.createElement('div');
      card.className = 'pixel-gallery-card-item checkerboard';
      card.dataset.assetId = asset.asset_id;

      // Render thumbnail image path
      const imgPath = '/file/' + asset.outputs.png;
      let label = asset.role || `Asset #${idx + 1}`;
      if (asset.prompt.includes("front view")) label = "Front";
      else if (asset.prompt.includes("right side")) label = "Right";
      else if (asset.prompt.includes("back view")) label = "Back";
      else if (asset.prompt.includes("left side")) label = "Left";

      card.innerHTML = `
        <img src="${imgPath}" alt="" />
        <span>${label}</span>
      `;

      card.addEventListener('click', () => {
        if (isEditing) {
          toast("Please exit or save edit mode before selecting a different asset.");
          return;
        }

        $$('.pixel-gallery-card-item').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        selectAsset(asset);
      });

      container.appendChild(card);
    });

    if (assets.length > 0) {
      // Auto-select first asset
      const firstCard = container.querySelector('.pixel-gallery-card-item');
      if (firstCard) firstCard.click();
    }
  }

  function selectAsset(asset) {
    activeAsset = asset;
    activeBatch = asset.manifest || null;
    currentCompareMode = 'normalized';

    // Clear active animation states
    activeAnimation = null;
    stopAnimPlayer();
    $('#pixelAnimationPlayToggleRow').style.display = 'none';
    $('#qaAnimationRows').style.display = 'none';
    $('#pixelTransferCompareRow').style.display = 'none';

    // Show compare toggle controls
    const compareRow = $('#pixelCompareToggleRow');
    if (compareRow) compareRow.style.display = 'flex';

    // Reset comparison active tab buttons
    const btnNormalized = $('#btnPreviewShowNormalized');
    const btnRaw = $('#btnPreviewShowRaw');
    if (btnNormalized) btnNormalized.classList.add('active');
    if (btnRaw) btnRaw.classList.remove('active');

    // Show/Hide Stitched sheet view selectors
    const sheetToggleRow = $('#pixelSheetViewToggleRow');
    if (sheetToggleRow) {
      if (activeBatch || asset.batch_id) {
        sheetToggleRow.style.display = 'flex';
        currentViewMode = 'sheet';
        const btnShowSheet = $('#btnPreviewShowSheet');
        const btnShowSingle = $('#btnPreviewShowSingle');
        if (btnShowSheet) btnShowSheet.classList.add('active');
        if (btnShowSingle) btnShowSingle.classList.remove('active');
      } else {
        sheetToggleRow.style.display = 'none';
        currentViewMode = 'single';
      }
    }

    // Toggle Seam Previewer button (Phase 6)
    const seamBtn = $('#pixelSeamPreviewBtn');
    if (seamBtn) {
      if (asset.asset_type === 'tileset') {
        seamBtn.style.display = 'block';
      } else {
        seamBtn.style.display = 'none';
        seamPreviewOn = false;
        seamBtn.textContent = 'Seam Preview: OFF';
      }
    }

    // Show/Hide skeletal joint handles overlays (Phase 11)
    const rigOverlay = $('#pixelRigOverlayContainer');
    if (rigOverlay) {
      if (asset.asset_type === 'characters') {
        rigOverlay.style.display = 'block';
        // Reset and align joint overlay transforms
        sliderHead.value = rigKeyframes[activeRigKeyframe].angles.head;
        sliderLeft.value = rigKeyframes[activeRigKeyframe].angles.arm_left;
        sliderRight.value = rigKeyframes[activeRigKeyframe].angles.arm_right;
        syncRigOverlayRotations();
      } else {
        rigOverlay.style.display = 'none';
      }
    }

    // Show "Re-normalize" action button
    const normBtn = $('#pixelNormalizeTriggerBtn');
    if (normBtn) normBtn.style.display = 'block';

    // Keep pack export button visible if activePack is set
    const packExpBtn = $('#inspectorExportPackBtn');
    if (packExpBtn && activePack) {
      packExpBtn.style.display = 'block';
      packExpBtn.disabled = false;
    }

    syncComparePreview();
    populateInspector(asset);
    compareActiveAssetToStyle();
  }

  function syncComparePreview() {
    if (!activeAsset) return;

    const fallback = $('#pixelSpriteFallback');
    const spriteImg = $('#pixelSpriteImg');
    const spriteContainer = $('#pixelSpriteContainer');
    const interactiveSvg = $('#pixelInteractiveSvg');

    if (fallback) fallback.style.display = 'none';
    if (interactiveSvg) interactiveSvg.remove();

    if (spriteImg && spriteContainer) {
      let relativePath = '';
      if (currentViewMode === 'sheet' && (activeBatch || activeAsset.batch_id)) {
        // Display packed composite sheet
        const bId = activeBatch ? activeBatch.batch_id : activeAsset.batch_id;
        relativePath = `output/pixel_assets/batches/${bId}/sheet.png`;
      } else {
        // Display individual direction sprite
        if (currentCompareMode === 'normalized') {
          relativePath = activeAsset.outputs.png;
        } else {
          const parts = activeAsset.outputs.png.split('/');
          parts[parts.length - 1] = 'raw.png';
          relativePath = parts.join('/');
        }
      }

      if (seamPreviewOn && activeAsset.asset_type === 'tileset') {
        // Render 3x3 repeating tile grid preview
        spriteImg.style.display = 'none';
        spriteContainer.style.backgroundImage = `url('/file/${relativePath}?t=${Date.now()}')`;
        spriteContainer.style.backgroundRepeat = 'repeat';
        spriteContainer.style.backgroundPosition = 'center';
        
        const w = activeAsset.resolution[0];
        const h = activeAsset.resolution[1];
        spriteContainer.style.backgroundSize = `${w}px ${h}px`;
        spriteContainer.style.width = `${w * 3}px`;
        spriteContainer.style.height = `${h * 3}px`;
      } else {
        // Restore standard single image view
        spriteImg.style.display = 'block';
        spriteContainer.style.backgroundImage = 'none';
        spriteContainer.style.width = '128px';
        spriteContainer.style.height = '128px';
        spriteImg.src = '/file/' + relativePath + '?t=' + Date.now();
      }
    }
  }

  function populateInspector(asset) {
    // Basic Metadata
    $('#inspectorAssetId').textContent = asset.asset_id;
    $('#inspectorMode').textContent = asset.mode || 'standard';
    
    // Display tile role if present
    const roleRow = $('#inspectorRoleRow');
    if (roleRow) {
      if (asset.role) {
        roleRow.style.display = 'block';
        $('#inspectorRole').textContent = asset.role;
      } else {
        roleRow.style.display = 'none';
      }
    }

    $('#inspectorDimensions').textContent = `${asset.resolution[0]}x${asset.resolution[1]}`;
    $('#inspectorModel').textContent = asset.model;

    // Display LoRA Row if present in the metadata
    const loraRow = $('#inspectorLoraRow');
    if (loraRow) {
      if (asset.lora_config) {
        loraRow.style.display = 'block';
        $('#inspectorLoraDetails').textContent = `${asset.lora_config.lora_name} (w: ${asset.lora_config.lora_weight})`;
      } else {
        loraRow.style.display = 'none';
      }
    }

    // Palette Colors
    const paletteContainer = $('#inspectorPaletteColors');
    if (paletteContainer) {
      paletteContainer.innerHTML = '';
      const colors = asset.palette.colors || [];
      if (colors.length === 0) {
        paletteContainer.innerHTML = '<div style="color: var(--muted); font-size: 11px;">No colors parsed</div>';
      } else {
        colors.forEach((col, cIdx) => {
          const div = document.createElement('div');
          div.style.width = '18px';
          div.style.height = '18px';
          div.style.background = col;
          div.style.borderRadius = '3px';
          div.style.cursor = 'pointer';
          div.title = col;
          
          // Set initial active color to the first color in the palette
          if (cIdx === 0 && !activeColor) activeColor = col;

          div.addEventListener('click', () => {
            activeColor = col;
            toast(`Active drawing color set: ${col}`);
            $$('#inspectorPaletteColors div').forEach(d => d.style.boxShadow = 'none');
            div.style.boxShadow = '0 0 0 2px var(--cyan)';
          });
          paletteContainer.appendChild(div);
        });
      }
    }

    // QA Gates status
    const countBadge = $('#qaColorCountBadge');
    if (countBadge) {
      const limit = asset.palette.max_colors || 24;
      const count = asset.qa.color_count || 0;
      countBadge.textContent = `${count} / ${limit}`;
      countBadge.className = count <= limit ? "badge qa-pass" : "badge qa-fail";
    }

    const alphaBadge = $('#qaAlphaBadge');
    if (alphaBadge) {
      const alphaOk = asset.qa.alpha_ok !== false;
      alphaBadge.textContent = alphaOk ? "PASS" : "FAIL";
      alphaBadge.className = alphaOk ? "badge qa-pass" : "badge qa-fail";
    }

    const blurBadge = $('#qaBlurBadge');
    if (blurBadge) {
      const blur = asset.qa.blur_score || 0;
      blurBadge.textContent = blur.toFixed(2);
      blurBadge.className = blur < 0.1 ? "badge qa-pass" : "badge qa-warn";
    }

    // Rotation Consistency Scores (Phase 3)
    const consistencyRows = $('#qaConsistencyRows');
    if (consistencyRows) {
      const bObj = activeBatch || asset.manifest || null;
      if (bObj && bObj.qa && bObj.qa.consistency_scores) {
        consistencyRows.style.display = 'flex';
        const scores = bObj.qa.consistency_scores;
        
        $('#qaPaletteSimilarity').textContent = `${(scores.palette_overlap * 100).toFixed(0)}%`;
        $('#qaHeightSimilarity').textContent = `${(scores.height_consistency * 100).toFixed(0)}%`;
        
        const overallEl = $('#qaOverallSimilarity');
        if (overallEl) {
          overallEl.textContent = `${(scores.overall * 100).toFixed(0)}%`;
          overallEl.className = scores.overall >= 0.8 ? "badge qa-pass" : "badge qa-fail";
        }
      } else {
        consistencyRows.style.display = 'none';
      }
    }

    // Seam QA Rows (Phase 6)
    const seamRows = $('#qaSeamRows');
    if (seamRows) {
      if (asset.qa && asset.qa.seam_check) {
        seamRows.style.display = 'flex';
        const lr = asset.qa.seam_check.left_right_delta;
        const tb = asset.qa.seam_check.top_bottom_delta;
        
        $('#qaHorizSeam').textContent = `${(lr * 100).toFixed(1)}% diff`;
        $('#qaVertSeam').textContent = `${(tb * 100).toFixed(1)}% diff`;
      } else {
        seamRows.style.display = 'none';
      }
    }

    // Actions
    $('#inspectorUseAsStyleBtn').disabled = false;
    $('#inspectorGenerateLikeBtn').disabled = false;
    $('#inspectorReskinBtn').disabled = false;
    $('#inspectorMatchStyleBtn').disabled = false;
    $('#inspectorApplyPartBtn').disabled = false;
    $('#inspectorCleanupBtn').disabled = false;
    $('#inspectorEditBtn').disabled = false;
    $('#inspectorExportBtn').disabled = false;
  }

  function renderPartVariants(variants) {
    const grid = $('#pixelPartVariantGrid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!variants.length) {
      grid.innerHTML = '<div style="font-size: 12px; color: var(--muted); grid-column: 1 / -1;">No variants returned.</div>';
      return;
    }
    variants.forEach((variant) => {
      const card = document.createElement('div');
      card.style.cssText = 'border:1px solid rgba(85,241,255,0.18); border-radius:8px; padding:8px; background:rgba(0,0,0,0.22); display:flex; flex-direction:column; gap:6px;';
      const img = document.createElement('img');
      img.src = `/file/${variant.path}?t=${Date.now()}`;
      img.alt = variant.variant_id;
      img.style.cssText = 'width:100%; aspect-ratio:1; object-fit:contain; image-rendering:pixelated; background:#05070d;';
      const note = document.createElement('div');
      note.textContent = variant.recommendation || variant.variant_id;
      note.style.cssText = 'font-size:11px; color:var(--muted); min-height:28px;';
      const accept = document.createElement('button');
      accept.className = 'mini primary';
      accept.type = 'button';
      accept.textContent = 'Accept';
      accept.addEventListener('click', async () => {
        if (!activeAsset) return;
        try {
          const res = await api('/api/pixel-assets/part/accept', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              variant_path: variant.path,
              label: variant.recommendation || 'applied part'
            })
          });
          if (res.ok) {
            activeAsset = res.asset;
            toast('Part applied to selected asset.');
            selectAsset(activeAsset);
            $('#pixelPartApplyModal')?.classList.add('hidden');
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
      card.appendChild(img);
      card.appendChild(note);
      card.appendChild(accept);
      grid.appendChild(card);
    });
  }

  function renderReskinVariants(variants) {
    const grid = $('#pixelReskinVariantGrid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!variants.length) {
      grid.innerHTML = '<div style="font-size: 12px; color: var(--muted); grid-column: 1 / -1;">No variants returned.</div>';
      return;
    }
    variants.forEach((variant) => {
      const card = document.createElement('div');
      card.style.cssText = 'border:1px solid rgba(85,241,255,0.18); border-radius:8px; padding:8px; background:rgba(0,0,0,0.22); display:flex; flex-direction:column; gap:6px;';
      const img = document.createElement('img');
      img.src = `/file/${variant.path}?t=${Date.now()}`;
      img.alt = variant.variant_id;
      img.style.cssText = 'width:100%; aspect-ratio:1; object-fit:contain; image-rendering:pixelated; background:#05070d;';
      const note = document.createElement('div');
      note.textContent = variant.recommendation || variant.variant_id;
      note.style.cssText = 'font-size:11px; color:var(--muted); min-height:28px;';
      const accept = document.createElement('button');
      accept.className = 'mini primary';
      accept.type = 'button';
      accept.textContent = 'Accept';
      accept.addEventListener('click', async () => {
        if (!activeAsset) return;
        try {
          const res = await api('/api/pixel-assets/reskin/accept', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              asset_id: activeAsset.asset_id,
              variant_path: variant.path,
              label: variant.recommendation || 'accepted reskin'
            })
          });
          if (res.ok) {
            activeAsset = res.asset;
            toast('Reskin applied to selected asset.');
            selectAsset(activeAsset);
            $('#pixelReskinModal')?.classList.add('hidden');
          } else {
            showPixelFailure(res.message);
          }
        } catch (err) {
          showPixelFailure(err.message);
        }
      });
      card.appendChild(img);
      card.appendChild(note);
      card.appendChild(accept);
      grid.appendChild(card);
    });
  }

  function readFileDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result || '');
      reader.onerror = () => reject(reader.error || new Error('Could not read file.'));
      reader.readAsDataURL(file);
    });
  }

  async function compareActiveAssetToStyle(showToast) {
    if (!activeAsset) return;
    const styleId = $('#pixelStyleProfileSelect')?.value || '';
    const consistencyRows = $('#qaConsistencyRows');
    if (!styleId) {
      if (consistencyRows && !(activeBatch && activeBatch.qa && activeBatch.qa.consistency_scores)) {
        consistencyRows.style.display = 'none';
      }
      return;
    }

    try {
      const res = await api('/api/pixel-assets/style/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: activeAsset.asset_id,
          style_id: styleId
        })
      });
      if (!res.ok) {
        if (showToast) showPixelFailure(res.message);
        return;
      }
      const match = res.match;
      if (consistencyRows) consistencyRows.style.display = 'flex';
      $('#qaPaletteSimilarity').textContent = `${(match.palette_overlap * 100).toFixed(0)}%`;
      $('#qaHeightSimilarity').textContent = `${(match.size_match * 100).toFixed(0)}%`;
      const overallEl = $('#qaOverallSimilarity');
      if (overallEl) {
        overallEl.textContent = `${(match.overall * 100).toFixed(0)}%`;
        overallEl.className = match.ok ? 'badge qa-pass' : 'badge qa-warn';
      }
      if (showToast) {
        toast(match.ok ? 'Selected asset matches the project style.' : 'Selected asset may need style repair.');
      }
    } catch (err) {
      if (showToast) showPixelFailure(err.message);
    }
  }

  async function triggerReNormalization() {
    if (!activeAsset) return;

    // Build normalization parameters from the active sidebar checkboxes
    const resolutionVal = $('#pixelResolutionSelect').value;
    const cleanAlpha = $('#pixelCleanAlphaToggle').checked;
    const quantizePalette = $('#pixelQuantizeToggle').checked;
    const maxColors = $('#pixelPaletteSizeSelect').value;
    const removeIslands = $('#pixelRemoveIslandsToggle').checked;
    const outline = $('#pixelOutlineSelect').value;

    const parts = activeAsset.outputs.png.split('/');
    parts[parts.length - 1] = 'raw.png';
    const rawPath = parts.join('/');

    const payload = {
      path: rawPath,
      resolution: resolutionVal,
      clean_alpha: cleanAlpha,
      quantize_palette: quantizePalette,
      max_colors: maxColors,
      remove_islands: removeIslands,
      min_island_size: 2,
      outline: outline
    };

    try {
      const res = await api('/api/pixel-assets/normalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        toast('Re-normalization completed!');
        
        // Update active asset outputs and trigger reload
        activeAsset.outputs.png = res.normalized_path;
        currentCompareMode = 'normalized';
        syncComparePreview();
      } else {
        showPixelFailure(res.message);
      }
    } catch (err) {
      showPixelFailure(err.message);
    }
  }

  async function cleanupSelectedAsset() {
    if (!activeAsset) {
      toast('Select an asset first.');
      return;
    }
    const payload = {
      asset_id: activeAsset.asset_id,
      remove_background: true,
      resolution: $('#pixelResolutionSelect')?.value || activeAsset.resolution?.join('x') || '32x32',
      clean_alpha: $('#pixelCleanAlphaToggle')?.checked ?? true,
      quantize_palette: $('#pixelQuantizeToggle')?.checked ?? true,
      max_colors: $('#pixelPaletteSizeSelect')?.value || activeAsset.palette?.max_colors || 24,
      remove_islands: $('#pixelRemoveIslandsToggle')?.checked ?? true,
      min_island_size: 2,
      outline: $('#pixelOutlineSelect')?.value || 'none'
    };
    toast('Cleaning selected pixel asset...');
    try {
      const res = await api('/api/pixel-assets/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        activeAsset = res.asset;
        currentCompareMode = 'normalized';
        toast('Cleanup completed and previous image versioned.');
        selectAsset(activeAsset);
      } else {
        showPixelFailure(res.message);
      }
    } catch (err) {
      showPixelFailure(err.message);
    }
  }

  if (window.onSpriteForgeReady) {
    window.onSpriteForgeReady(initPixelStudio);
  } else {
    document.addEventListener('DOMContentLoaded', initPixelStudio);
  }
})();
