"""The dial each late act asks you to manage.

A dial is the difference between an act you buy through and an act you play:
turn it up for more output now and more of whatever it costs you later.
"""

from pclengine.core.acts import Dial

DIALS = [
    Dial("overdrive", 4, "Overdrive",
         "Push the lifting rigs past their rating.",
         "more mass per rig, and far more heat"),
    Dial("partition", 7, "Partitioning",
         "Split the machine into more, smaller domains.",
         "less latency, fewer domains doing work"),
    Dial("aggression", 9, "Aggression",
         "How hard to push edits into the constants.",
         "faster progress, stability falls quicker"),
]
