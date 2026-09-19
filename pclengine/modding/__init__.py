"""Loading content.

The base game and every mod come through the same door: a package with a
`register(api)` function, handed a `ModAPI` that is the only supported way
to reach into the engine.

    api      what a mod is allowed to do
    loader   finding mods, loading them, and putting everything back
    package  the .mpkg format -- an uncompressed zip holding a package
"""
