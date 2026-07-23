"""
Network centrality over a participant's belief network.

Computes weighted degree and weighted eigenvector centrality on the
undirected graph formed by the nodes (statements) and the edges the
participant drew. Edges of every type are treated the same and weighted
by their strength rating; multiple edges between the same pair are summed.

Stored on the player and included in the data export - not shown to the
participant. Kept simple on purpose; it is a blueprint for measures the
researchers may refine later.
"""

import math


def compute_centrality(node_labels, edges, weighted=True):
    labels = list(dict.fromkeys(node_labels))
    n = len(labels)
    index = {lab: i for i, lab in enumerate(labels)}

    adjacency = [[0.0] * n for _ in range(n)]
    seen = set()
    for edge in edges:
        a = edge.get("stance_1")
        b = edge.get("stance_2")
        if a not in index or b not in index or a == b:
            continue
        # The same edge can be stored on more than one page (prior edges are
        # merged forward), so skip pairs of the same type we've already counted.
        key = (frozenset((a, b)), edge.get("polarity"))
        if key in seen:
            continue
        seen.add(key)
        weight = _edge_weight(edge) if weighted else 1.0
        i, j = index[a], index[b]
        adjacency[i][j] += weight
        adjacency[j][i] += weight

    degree = [sum(row) for row in adjacency]
    eigenvector = _principal_eigenvector(adjacency)

    nodes = [
        {
            "label": labels[i],
            "degree": round(degree[i], 4),
            "eigenvector": round(eigenvector[i], 4),
        }
        for i in range(n)
    ]

    return {
        "measures": ["degree", "eigenvector"],
        "weighted": weighted,
        "nodes": nodes,
        "top_degree": _top(nodes, "degree"),
        "top_eigenvector": _top(nodes, "eigenvector"),
    }


def _edge_weight(edge):
    try:
        return float(edge.get("strength"))
    except (TypeError, ValueError):
        return 1.0


def _principal_eigenvector(adjacency, iterations=1000, tol=1e-12):
    n = len(adjacency)
    if n == 0:
        return []
    # Iterate on (A + shift*I) instead of A. Shifting by the spectral-radius
    # bound keeps A's eigenvectors but makes the largest eigenvalue strictly
    # dominant, so power iteration converges instead of oscillating on
    # bipartite graphs (stars, paths).
    shift = max((sum(abs(v) for v in row) for row in adjacency), default=0.0) or 1.0
    x = [1.0] * n
    for _ in range(iterations):
        y = [
            sum(adjacency[i][j] * x[j] for j in range(n)) + shift * x[i]
            for i in range(n)
        ]
        norm = math.sqrt(sum(v * v for v in y))
        if norm == 0:
            return [0.0] * n
        y = [v / norm for v in y]
        if max(abs(y[i] - x[i]) for i in range(n)) < tol:
            x = y
            break
        x = y
    if x and x[0] < 0:
        x = [-v for v in x]
    return x


def _top(nodes, key):
    if not nodes:
        return None
    best = max(nodes, key=lambda node: node[key])
    return {"label": best["label"], "value": best[key]}
