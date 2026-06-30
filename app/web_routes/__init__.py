# Web routes blueprints package
from .routes_jobs import routes_jobs
from .routes_projects import routes_projects
from .routes_sprites import routes_sprites
from .routes_misc import routes_misc
from .routes_static import routes_static

__all__ = ["routes_jobs", "routes_projects", "routes_sprites", "routes_misc", "routes_static"]
