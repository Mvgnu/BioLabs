from importlib import import_module

modules = [
    'auth',
    'users',
    'inventory',
    'fields',
    'locations',
    'teams',
    'files',
    'protocols',
    'troubleshooting',
    'notebook',
    'comments',
    'notifications',
    'schedule',
    'sequence',
    'projects',
    'assistant',
    'calendar',
    'tools',
    'search',
    'analytics',
    'audit',
    'equipment',
    'experiment_console',
    'compliance',
    'external',
    'data_analysis',
    'labs',
    'resource_shares',
    'marketplace',
    'services',
    'knowledge',
    'forum',
    'community',
    'workflows',
]

for m in modules:
    import_module(f'.{m}', __name__)

__all__ = modules
