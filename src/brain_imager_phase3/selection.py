from .assets import decoded_rows, validate_phase2
from .common import digest, load_json, require, save_json

def create_selection(cfg):
    validate_phase2(cfg)
    groups = load_json(cfg.phase2 / "results/target_similarity_groups.json")["components"]
    ordered = sorted(groups, key=lambda g: digest([cfg.raw["selection_seed"], sorted(g)]))
    selected = []
    for group in ordered:
        if len(selected) + len(group) <= cfg.raw["pilot_size"]:
            selected.extend(group)
        if len(selected) == cfg.raw["pilot_size"]:
            break
    require(len(selected) == cfg.raw["pilot_size"], "Could not fill pilot without splitting a similarity group")
    target_set = {i for g in groups for i in g}
    obj = {"schema_version": 1, "purpose": "Phase 3 exploratory pilot; not confirmatory",
           "seed": cfg.raw["selection_seed"], "requested_size": cfg.raw["pilot_size"],
           "decoders": cfg.raw["decoders"], "coco_image_ids": selected,
           "reserved_coco_image_ids": sorted(target_set - set(selected)),
           "selection_rule": "SHA-256 order of whole Phase 2 similarity groups; no selection by caption errors or outputs"}
    obj["selection_sha256"] = digest(obj)
    path = cfg.study / "selection.json"
    if path.exists():
        require(load_json(path) == obj, "Pilot selection is frozen. Use a new workspace for a separately identified pilot; do not overwrite.")
    else:
        save_json(path, obj)
    return obj

def load_selection(cfg):
    obj = load_json(cfg.study / "selection.json")
    require(obj["selection_sha256"] == digest({k: v for k, v in obj.items() if k != "selection_sha256"}), "Selection hash mismatch")
    require(obj["decoders"] == cfg.raw["decoders"] and obj["seed"] == cfg.raw["selection_seed"] and obj["requested_size"] == cfg.raw["pilot_size"], "Config no longer matches frozen pilot")
    return obj

def pilot_rows(cfg):
    ids = set(load_selection(cfg)["coco_image_ids"])
    return [r for r in decoded_rows(cfg) if r["coco_image_id"] in ids]
