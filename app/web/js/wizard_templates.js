(function () {
  'use strict';

  const templates = {
      platformer: {
        style: 'polished 2D platformer sprite, professional character design, readable side-view silhouette, crisp pixel-friendly edges, locked camera',
        actions: ['idle', 'walk', 'run', 'jump', 'fall', 'land', 'attack_light', 'hurt', 'death'],
        directions: ['right'],
        perspective: 'side_view'
      },
      topdown: {
        style: 'polished top-down RPG sprite, professional character design, readable small-scale silhouette, consistent outfit, locked orthographic camera',
        actions: ['idle', 'walk', 'run', 'attack_light', 'cast', 'hurt', 'death'],
        directions: ['front', 'back', 'left', 'right'],
        perspective: 'isometric'
      },
      fighter: {
        style: 'polished fighting game sprite animation, professional character design, strong pose clarity, clean silhouette, consistent costume, locked camera',
        actions: ['idle', 'walk', 'run', 'attack_light', 'attack_heavy', 'block', 'dodge', 'hurt', 'death'],
        directions: ['right'],
        perspective: 'side_view'
      },
      enemy: {
        style: 'polished game enemy sprite, bold readable silhouette, strong shape language, clean animation poses, locked camera',
        actions: ['idle', 'walk', 'run', 'attack_light', 'hurt', 'death'],
        directions: ['right'],
        perspective: 'three_quarter'
      },
      object: {
        style: 'polished game object sprite animation, centered object, clean outline, cohesive palette, locked camera, transparent-ready background',
        actions: ['idle', 'use', 'interact'],
        directions: ['front'],
        perspective: 'orthographic'
      }
  };
  const perspectivePrompts = {
      side_view: 'side-view camera, horizontal profile, locked 2D view',
      front_view: 'front-facing camera, centered character, locked 2D view',
      back_view: 'back-facing camera, centered character, locked 2D view',
      three_quarter: 'three-quarter camera, readable depth, locked camera',
      top_down: 'top-down camera, map-ready silhouette, locked overhead view',
      isometric: 'isometric camera projection, game-ready diagonal view, locked camera',
      orthographic: 'orthographic camera, no perspective distortion, locked view',
      low_angle: 'low-angle heroic camera, consistent sprite framing, locked camera',
      high_angle: 'high-angle camera, readable top surfaces, locked camera',
      overhead: 'direct overhead camera, tactical readable silhouette, locked camera'
  };

  function applyTemplateDefaults(templateName, handlers) {
    const template = templates[templateName];
    if (!template) return false;
    handlers.setSelectedActions(template.actions);
    handlers.setSelectedDirections(template.directions || ['right']);
    handlers.setSelectedPerspective(template.perspective || 'side_view');
    if (typeof handlers.onApplied === 'function') handlers.onApplied(template);
    return true;
  }

  function buildPromptPreviewText(context) {
    const template = templates[context.templateName] || templates.platformer;
    const perspectivePrompt = perspectivePrompts[context.perspective] || perspectivePrompts.side_view;
    const style = template?.style || '';
    let previewText = `Character Name: ${context.name || 'hero'}\n`;
    previewText += `Description: ${context.desc || '...'}\n`;
    previewText += `Style Inject: ${style}, ${perspectivePrompt}\n`;
    previewText += `Reference Image: ${context.referenceImage || 'none'}\n`;
    previewText += `Style Reference: ${context.styleImage || 'none'}\n`;
    previewText += `Primary Direction: ${context.direction || 'right'}\n`;
    previewText += `Camera Perspective: ${String(context.perspective || 'side_view').replace(/_/g, ' ')}`;
    return previewText;
  }

  window.SpriteForgeWizardTemplates = {
    templates,
    perspectivePrompts,
    applyTemplateDefaults,
    buildPromptPreviewText
  };
})();
