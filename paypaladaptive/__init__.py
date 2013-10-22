__version__ = (0, 2, 0)

try:
    import settings

    if settings.USE_DELAYED_UPDATES:
        import receivers
except ImportError:
    pass
