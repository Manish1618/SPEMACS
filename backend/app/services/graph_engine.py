import networkx as nx
from typing import Dict, List, Any, Optional
from rapidfuzz import fuzz
import math

class TemporalKnowledgeGraph:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.entity_lookup: Dict[str, Dict[str, Any]] = {}
        self.aliases: Dict[str, str] = {} # alias_name -> canonical_id
        
    def clear(self):
        self.graph.clear()
        self.entity_lookup.clear()
        self.aliases.clear()

    def add_entity(
        self,
        entity_id: str,
        label: str,
        entity_type: str,
        case_id: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        props = dict(properties or {})
        props["case_id"] = case_id
        props["entity_type"] = entity_type
        props["label"] = label
        
        self.graph.add_node(entity_id, **props)
        self.entity_lookup[entity_id] = {
            "id": entity_id,
            "label": label,
            "entity_type": entity_type,
            "case_id": case_id,
            "properties": props
        }
        
        # Track aliases if present
        if "aliases" in props and isinstance(props["aliases"], list):
            for alias in props["aliases"]:
                self.aliases[alias.lower().strip()] = entity_id
                
        return entity_id

    def add_relationship(
        self,
        rel_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        case_id: str,
        confidence: float = 1.0,
        evidence_ids: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        props = dict(properties or {})
        props["case_id"] = case_id
        props["label"] = rel_type
        props["rel_type"] = rel_type
        props["confidence"] = confidence
        props["evidence_ids"] = evidence_ids or []
        
        self.graph.add_edge(
            source_id,
            target_id,
            key=rel_id,
            **props
        )

    def resolve_entity(self, query_str: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query_clean = query_str.lower().strip()
        matches = []
        
        # 1. Check exact alias or ID match
        if query_clean in self.aliases:
            canonical_id = self.aliases[query_clean]
            node_data = self.entity_lookup.get(canonical_id)
            if node_data:
                matches.append({
                    "entity": node_data,
                    "confidence": 0.98,
                    "match_type": "EXACT_ALIAS_MATCH",
                    "requires_verification": False
                })
                
        for entity_id, data in self.entity_lookup.items():
            if entity_type and data["entity_type"] != entity_type:
                continue
                
            label = data["label"].lower()
            score = fuzz.token_sort_ratio(query_clean, label) / 100.0
            
            # Check properties (e.g. phone, plate)
            for k, v in data["properties"].items():
                if isinstance(v, str) and query_clean in v.lower():
                    score = max(score, 0.95)
                    
            if score >= 0.70 and not any(m["entity"]["id"] == entity_id for m in matches):
                matches.append({
                    "entity": data,
                    "confidence": round(score, 2),
                    "match_type": "FUZZY_NAME_MATCH" if score < 0.90 else "HIGH_CONFIDENCE_MATCH",
                    "requires_verification": score < 0.90
                })
                
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches

    def get_case_subgraph(self, case_id: str) -> Dict[str, Any]:
        nodes = {n for n, d in self.graph.nodes(data=True) if d.get("case_id") == case_id}
        if not nodes:
            nodes = set(self.graph.nodes())
        return self._build_subgraph_response(nodes)

    def get_k_hop_neighborhood(self, entity_id: str, k: int = 2) -> Dict[str, Any]:
        if entity_id not in self.graph:
            return {"nodes": [], "edges": []}
            
        undirected = self.graph.to_undirected()
        subgraph_nodes = set([entity_id])
        current_layer = set([entity_id])
        
        for _ in range(k):
            next_layer = set()
            for node in current_layer:
                neighbors = set(undirected.neighbors(node))
                next_layer.update(neighbors - subgraph_nodes)
            subgraph_nodes.update(next_layer)
            current_layer = next_layer
            
        return self._build_subgraph_response(subgraph_nodes)

    def get_shortest_path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        if source_id not in self.graph or target_id not in self.graph:
            return {"path_found": False, "nodes": [], "edges": []}
            
        try:
            path_node_ids = nx.shortest_path(self.graph.to_undirected(), source=source_id, target=target_id)
            subgraph_res = self._build_subgraph_response(set(path_node_ids))
            subgraph_res["path_found"] = True
            subgraph_res["path_node_ids"] = path_node_ids
            return subgraph_res
        except nx.NetworkXNoPath:
            return {"path_found": False, "nodes": [], "edges": []}

    def compute_graph_analytics(self, case_id: Optional[str] = None) -> Dict[str, Any]:
        active_nodes = [n for n, d in self.graph.nodes(data=True) if not case_id or d.get("case_id") == case_id]
        sub = self.graph.subgraph(active_nodes).to_undirected()
        
        if len(sub.nodes) == 0:
            return {"degree_centrality": {}, "betweenness_centrality": {}, "hubs": [], "bridges": [], "communities": {}}
            
        degree_centrality = nx.degree_centrality(sub)
        betweenness = nx.betweenness_centrality(sub)
        
        # Hub nodes (top 15% degree centrality)
        sorted_deg = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)
        hubs = [node for node, score in sorted_deg[:max(2, int(len(sorted_deg) * 0.15))]]
        
        # Bridge nodes (top betweenness)
        sorted_bet = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
        bridges = [node for node, score in sorted_bet[:max(2, int(len(sorted_bet) * 0.15))]]
        
        # Basic connected components for community grouping
        components = list(nx.connected_components(sub))
        community_map = {}
        for comm_id, comp in enumerate(components):
            for node in comp:
                community_map[node] = comm_id
                
        return {
            "degree_centrality": degree_centrality,
            "betweenness_centrality": betweenness,
            "hubs": hubs,
            "bridges": bridges,
            "communities": community_map
        }

    def find_cross_case_overlaps(self) -> List[Dict[str, Any]]:
        overlaps = []
        for entity_id, data in self.entity_lookup.items():
            # Check incident edges across different cases
            connected_cases = set()
            if "case_id" in data:
                connected_cases.add(data["case_id"])
                
            for u, v, k, edata in self.graph.edges(entity_id, data=True, keys=True):
                if "case_id" in edata:
                    connected_cases.add(edata["case_id"])
                    
            if len(connected_cases) > 1:
                overlaps.append({
                    "entity_id": entity_id,
                    "label": data["label"],
                    "entity_type": data["entity_type"],
                    "cases": list(connected_cases),
                    "insight": f"Cross-case entity '{data['label']}' appears across multiple active/archived investigations: {', '.join(connected_cases)}."
                })
        return overlaps

    def detect_anomalies(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anomalies = []
        sorted_events = sorted(events, key=lambda x: x.get("timestamp", ""))
        
        # 1. Impossible Travel Anomaly Check
        entity_events: Dict[str, List[Dict[str, Any]]] = {}
        for evt in sorted_events:
            for ent in evt.get("related_entities", []):
                entity_events.setdefault(ent, []).append(evt)
                
        for ent, evts in entity_events.items():
            for i in range(len(evts) - 1):
                e1 = evts[i]
                e2 = evts[i+1]
                if "latitude" in e1 and "latitude" in e2 and e1.get("latitude") and e2.get("latitude"):
                    lat1, lon1 = e1["latitude"], e1["longitude"]
                    lat2, lon2 = e2["latitude"], e2["longitude"]
                    dist = self._haversine(lat1, lon1, lat2, lon2)
                    
                    t1 = e1.get("timestamp")
                    t2 = e2.get("timestamp")
                    if t1 and t2:
                        try:
                            from datetime import datetime
                            dt1 = datetime.fromisoformat(str(t1).replace("Z", "+00:00"))
                            dt2 = datetime.fromisoformat(str(t2).replace("Z", "+00:00"))
                            hours = max(0.01, (dt2 - dt1).total_seconds() / 3600.0)
                            speed = dist / hours
                            if speed > 850.0 and dist > 100:
                                anomalies.append({
                                    "anomaly_type": "IMPOSSIBLE_TRAVEL_SPEED",
                                    "entity": ent,
                                    "event_1": e1["title"],
                                    "event_2": e2["title"],
                                    "distance_km": round(dist, 1),
                                    "time_span_hours": round(hours, 2),
                                    "implied_speed_kmh": round(speed, 1),
                                    "description": f"Entity '{ent}' recorded at {e1.get('location_name', 'Loc 1')} and {e2.get('location_name', 'Loc 2')} ({round(dist)}km apart) within {round(hours, 1)} hrs. Implies SIM card handover or location spoofing."
                                })
                        except Exception:
                            pass
        return anomalies

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _build_subgraph_response(self, node_ids: set) -> Dict[str, Any]:
        nodes_out = []
        edges_out = []
        analytics = self.compute_graph_analytics()
        
        for n in node_ids:
            if n in self.graph:
                ndata = self.graph.nodes[n]
                nodes_out.append({
                    "id": n,
                    "label": ndata.get("label", n),
                    "entity_type": ndata.get("entity_type", "Entity"),
                    "properties": {k: v for k, v in ndata.items() if k not in ["label", "entity_type"]},
                    "is_hub": n in analytics["hubs"],
                    "is_bridge": n in analytics["bridges"],
                    "centrality_score": round(analytics["degree_centrality"].get(n, 0.0), 3),
                    "community_id": analytics["communities"].get(n, 0)
                })
                
        sub = self.graph.subgraph(node_ids)
        for u, v, k, edata in sub.edges(data=True, keys=True):
            edges_out.append({
                "id": str(k),
                "source": u,
                "target": v,
                "label": edata.get("label", "RELATED_TO"),
                "relationship_type": edata.get("rel_type", "RELATED_TO"),
                "confidence": edata.get("confidence", 1.0),
                "evidence_ids": edata.get("evidence_ids", []),
                "properties": {k: v for k, v in edata.items() if k not in ["label", "rel_type", "confidence", "evidence_ids"]}
            })
            
        return {
            "nodes": nodes_out,
            "edges": edges_out,
            "stats": {
                "total_nodes": len(nodes_out),
                "total_edges": len(edges_out),
                "hubs_count": len([n for n in nodes_out if n["is_hub"]]),
                "bridges_count": len([n for n in nodes_out if n["is_bridge"]])
            }
        }

knowledge_graph = TemporalKnowledgeGraph()
