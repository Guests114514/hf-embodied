import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

import config
import db

conn = db.connect()

G = nx.DiGraph()
for src, dst in conn.execute("SELECT src, dst FROM edges WHERE kind = 'follow'"):
    G.add_edge(src, dst)

seeds = {r[0] for r in db.top_users(conn, config.BULK_UPLOADER_MIN_MODELS, config.TOP_V)}
crawled = {r[0] for r in conn.execute("SELECT DISTINCT username FROM crawled")}

keep = [u for u, d in sorted(G.degree(), key=lambda kv: -kv[1])[:config.MAX_NODES]]
H = G.subgraph(keep).copy()
print(f"全图 {G.number_of_nodes()} 节点 / {G.number_of_edges()} 边；"
      f"画图取度数前 {config.MAX_NODES}，留下 {H.number_of_nodes()} 节点 "
      f"/ {H.number_of_edges()} 边")

nodes = list(H.nodes())
pos = nx.spring_layout(H, k=1.2, iterations=200, seed=7)
colors = ["#d62728" if u in seeds else "#ff7f0e" if u in crawled else "#9bb7d4"
          for u in nodes]
sizes = [70 + 45 * min(H.degree(u), 20) for u in nodes]
mutual = {e for e in H.edges() if H.has_edge(e[1], e[0])}
plain = [e for e in H.edges() if e not in mutual]

fig, ax = plt.subplots(figsize=(14, 10))
nx.draw_networkx_edges(H, pos, edgelist=plain, alpha=0.25, width=0.6,
                       edge_color="#7a869a", arrows=True, ax=ax)
nx.draw_networkx_edges(H, pos, edgelist=list(mutual), alpha=0.8, width=1.4,
                       edge_color="#2ca02c", arrows=True, ax=ax)
nx.draw_networkx_nodes(H, pos, nodelist=nodes, node_color=colors,
                       node_size=sizes, ax=ax)
labeled = sorted(nodes, key=lambda u: -H.degree(u))[:30]
nx.draw_networkx_labels(H, pos, labels={u: u for u in labeled}, font_size=8, ax=ax)
ax.set_title(f"Follow network: top {config.MAX_NODES} nodes by degree  "
             f"(red = top-10 seeds, orange = expanded hubs, green = mutual follow)")
ax.axis("off")
fig.tight_layout()
os.makedirs("static", exist_ok=True)
fig.savefig("static/graph.png", dpi=160)
print(f"saved static/graph.png | 双向关注的边 {len(mutual)} 条")
conn.close()