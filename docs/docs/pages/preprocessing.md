# Preprocessing

OSRM requires OSM data to be preprocessed before routing. Two algorithms are supported:

- **CH (Contraction Hierarchies)** — fastest query times; use `extract` → `contract`
- **MLD (Multi-Level Dijkstra)** — better for large networks and dynamic weights; use `extract` → `partition` → `customize`

---

## extract

::: osrm.extract
    options:
      show_root_heading: true

---

## contract

::: osrm.contract
    options:
      show_root_heading: true

---

## partition

::: osrm.partition
    options:
      show_root_heading: true

---

## customize

::: osrm.customize
    options:
      show_root_heading: true
