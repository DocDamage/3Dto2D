# Web routes blueprints package
from .routes_jobs import routes_jobs
from .routes_projects import routes_projects
from .routes_sprites import routes_sprites
from .routes_misc import routes_misc
from .routes_static import routes_static
from .routes_onboarding import routes_onboarding
from .routes_pixel_asset import routes_pixel_asset
from .routes_assets import routes_assets
from .routes_production import routes_production
from .routes_aaa import routes_aaa
from .routes_assistant import routes_assistant

__all__ = [
    "routes_jobs", "routes_projects", "routes_sprites",
    "routes_misc", "routes_static", "routes_onboarding",
    "routes_pixel_asset", "routes_assets", "routes_production", "routes_aaa",
    "routes_assistant"
]
