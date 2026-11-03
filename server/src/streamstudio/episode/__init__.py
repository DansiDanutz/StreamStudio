"""The episode factory: script in, private YouTube upload out.

Package rule (enforced by ``tests/test_episode_imports.py``): no module in this package imports
``cv2``, ``numpy``, ``scipy``, ``PIL``, ``rembg`` or ``playwright`` at module level. Handlers import
them inside the function body, as ``worker.handlers._cutout_clip`` does, so the API, the base
install and CI (which may lack the ``episode`` extra) can import every module here.

Stage 0 ships the package skeleton and ``preflight``. Later stages add the contract, the record,
the ledger, the planner and the handlers (see ``docs/egm/daily-episode-factory``).
"""

#: Every episode render runs at this frame rate: clips, cards, the intro and the final video.
FPS = 25

#: Parallel Chrome processes HyperFrames may use for one card render.
HYPERFRAMES_WORKERS = 4
