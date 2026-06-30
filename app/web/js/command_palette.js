(function() {
  let allCommands = [];
  let filteredCommands = [];
  let selectedIndex = -1;

  const modal = document.getElementById('commandPaletteModal');
  const backdrop = document.getElementById('commandPaletteBackdrop');
  const input = document.getElementById('commandPaletteInput');
  const resultsContainer = document.getElementById('commandPaletteResults');
  const closeBtn = document.getElementById('closeCommandPaletteBtn');

  function openPalette() {
    if (!modal) return;
    modal.classList.remove('hidden');
    input.value = '';
    selectedIndex = -1;
    input.focus();
    fetchCommands();
  }

  function closePalette() {
    if (!modal) return;
    modal.classList.add('hidden');
  }

  function fetchCommands() {
    api('/api/commands/list')
      .then(data => {
        if (data && data.ok) {
          allCommands = data.commands || [];
          renderCommands(allCommands);
        }
      })
      .catch(err => {
        console.error('Error fetching commands:', err);
        toast('Failed to load commands: ' + err.message);
      });
  }

  function renderCommands(commands) {
    filteredCommands = commands;
    resultsContainer.innerHTML = '';
    selectedIndex = -1;

    if (commands.length === 0) {
      resultsContainer.innerHTML = '<div style="color: var(--muted); padding: 12px; text-align: center; font-size: 13px;">No commands found.</div>';
      return;
    }

    commands.forEach((cmd, idx) => {
      const item = document.createElement('div');
      item.className = 'command-item';
      item.dataset.index = idx;

      // Styling
      item.style.padding = '10px 12px';
      item.style.borderRadius = '6px';
      item.style.cursor = 'pointer';
      item.style.transition = 'background 0.2s';
      item.style.display = 'flex';
      item.style.justifyContent = 'space-between';
      item.style.alignItems = 'center';

      if (!cmd.enabled) {
        item.style.opacity = '0.5';
        item.style.cursor = 'not-allowed';
      }

      // Left column: label and description
      const info = document.createElement('div');
      info.innerHTML = `<strong style="display:block; color: #fff; font-size: 13px;">${escapeHtml(cmd.label)}</strong>
                        <span style="font-size: 11px; color: var(--muted);">${escapeHtml(cmd.description || '')}</span>`;
      item.appendChild(info);

      // Right column: hints and tags
      const meta = document.createElement('div');
      meta.style.display = 'flex';
      meta.style.gap = '8px';
      meta.style.alignItems = 'center';

      if (cmd.view) {
        const tag = document.createElement('span');
        tag.style.background = 'rgba(0, 173, 181, 0.15)';
        tag.style.color = 'var(--accent)';
        tag.style.padding = '2px 6px';
        tag.style.borderRadius = '4px';
        tag.style.fontSize = '10px';
        tag.style.textTransform = 'uppercase';
        tag.textContent = cmd.view;
        meta.appendChild(tag);
      }

      if (cmd.requires_confirmation) {
        const confirmTag = document.createElement('span');
        confirmTag.style.background = 'rgba(255, 170, 0, 0.15)';
        confirmTag.style.color = '#ffaa00';
        confirmTag.style.padding = '2px 6px';
        confirmTag.style.borderRadius = '4px';
        confirmTag.style.fontSize = '10px';
        confirmTag.textContent = 'Confirm';
        meta.appendChild(confirmTag);
      }

      item.appendChild(meta);

      // Click handler
      item.addEventListener('click', () => {
        if (cmd.enabled) {
          executeCmd(cmd);
        } else {
          toast(cmd.disabled_reason || 'Command is currently disabled.');
        }
      });

      resultsContainer.appendChild(item);
    });

    updateSelection();
  }

  function updateSelection() {
    const items = resultsContainer.querySelectorAll('.command-item');
    items.forEach((item, idx) => {
      if (idx === selectedIndex) {
        item.style.background = 'rgba(255, 255, 255, 0.08)';
        item.scrollIntoView({ block: 'nearest' });
      } else {
        item.style.background = 'transparent';
      }
    });
  }

  function executeCmd(cmd) {
    closePalette();

    if (cmd.requires_confirmation) {
      const confirmRun = confirm(`Are you sure you want to run: "${cmd.label}"?\n\n${cmd.description}`);
      if (!confirmRun) return;
    }

    if (cmd.action_type === 'frontend_route' && cmd.view) {
      showView(cmd.view);
      toast(`Switched to ${cmd.view} view`);
    } else if (cmd.action_type === 'backend_action') {
      api(cmd.endpoint, { method: 'POST', body: JSON.stringify({ id: cmd.id }) })
        .then(data => {
          if (data && data.ok) {
            if (data.requires_confirmation) {
              const confirmServer = confirm(data.message || 'Execution requires confirmation. Proceed?');
              if (confirmServer) {
                api(cmd.endpoint, { method: 'POST', body: JSON.stringify({ id: cmd.id, confirmed: true }) })
                  .then(d => {
                    if (d.ok) toast(d.message || 'Command executed successfully.');
                    else toast('Error: ' + (d.message || 'Failed'));
                  });
              }
            } else {
              toast(data.message || 'Command executed successfully.');
              if (data.action && data.action.view) {
                showView(data.action.view);
              }
            }
          } else {
            toast('Error: ' + (data ? data.message : 'Unknown error'));
          }
        })
        .catch(err => {
          toast('Failed to run action: ' + err.message);
        });
    }
  }

  // Key Event bindings
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (modal.classList.contains('hidden')) {
        openPalette();
      } else {
        closePalette();
      }
    }
  });

  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    if (!q) {
      renderCommands(allCommands);
      return;
    }
    const filtered = allCommands.filter(c =>
      c.label.toLowerCase().includes(q) ||
      (c.description && c.description.toLowerCase().includes(q))
    );
    renderCommands(filtered);
  });

  input.addEventListener('keydown', e => {
    const items = resultsContainer.querySelectorAll('.command-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % items.length;
      updateSelection();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + items.length) % items.length;
      updateSelection();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < filteredCommands.length) {
        const cmd = filteredCommands[selectedIndex];
        if (cmd.enabled) executeCmd(cmd);
        else toast(cmd.disabled_reason || 'Command is currently disabled.');
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closePalette();
    }
  });

  if (closeBtn) closeBtn.addEventListener('click', closePalette);
  if (backdrop) backdrop.addEventListener('click', closePalette);

  window.CommandPalette = {
    open: openPalette,
    close: closePalette
  };
})();
