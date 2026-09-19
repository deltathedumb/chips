"""pclengine: an engine for paperclip-shaped idle games.

The engine owns the shape of such a game -- acts that hand off to one
another, a research tree that gates them, a project list, a war model, a
fixed-step clock, two front ends and a mod loader -- and owns none of the
subject matter. What the game is *about* arrives as content: the base mod in
`mods/base` is what makes this FOUNDRY, a game about silicon, and it uses
exactly the same API any other mod gets.

Importing the package loads content, because an engine with no acts in it is
not a game. Pass `no_base=True` to `loader.load` if you want the bare engine.
"""


from .modding import loader as _loader  # noqa: E402

_loader.ensure_loaded()
