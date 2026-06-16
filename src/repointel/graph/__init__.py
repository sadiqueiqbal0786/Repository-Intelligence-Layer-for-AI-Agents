"""Architecture graph layer (Phase 3).

Subpackages:
- ``builder`` — construct nodes (file/module/class/function/service/route/db)
  and edges (imports/calls/depends_on/implements/extends).
- ``traversal`` — query the graph (dependencies, consumers, critical paths).
- ``impact`` — change-impact analysis over the graph (Phase 9).
"""
