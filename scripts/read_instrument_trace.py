"""Read instrument_trace.jsonl and display all 5 representations for comparison."""
import json, os
from collections import defaultdict


def load_traces(logpath=None):
    if logpath is None:
        logpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "instrument_trace.jsonl")
    traces = defaultdict(list)
    try:
        with open(logpath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                traces[entry["trace_id"]].append(entry)
    except FileNotFoundError:
        print(f"Log file {logpath} not found — run an Auto Arrange first.")
        return {}
    return dict(traces)


def show_trace(trace_id, entries):
    print(f"\n{'='*100}")
    print(f"TRACE: {trace_id}")
    print(f"{'='*100}")

    # Group by rep number
    by_rep = defaultdict(list)
    for e in entries:
        by_rep[e["rep"]].append(e)

    for rep in sorted(by_rep.keys()):
        label_map = {
            1: "PLANNER RAW PLACEMENTS (before serialization)",
            2: "DB WRITES (rows inserted/updated)",
            3: "DB READS (rows read back by API)",
            4: "JSON SENT TO FRONTEND",
            5: "CANVAS RENDERED COORDINATES",
        }
        title = label_map.get(rep, f"REPRESENTATION {rep}")
        for entry in by_rep[rep]:
            print(f"\n--- {title} ({entry['label']}) ---")
            data = entry["data"]
            # Rep-99: vehicle summary lines (string list)
            if "summary_lines" in data:
                for l in data["summary_lines"]:
                    print(f"  {l}")
                print(f"  Total: {data.get('total_packages', '?')} packages in {data.get('vehicle_count', '?')} vehicles")
                continue

            placements = data.get("placements") or data.get("placements_written") or data.get("placements_read") or data.get("packages", [])
            # Print vehicle context
            if "vehicle_id" in data:
                vid = data.get("vehicle_id")
                pn = data.get("plate_number", "")
                print(f"  Vehicle: {vid} {pn}")
            if "per_vehicle" in data:
                for pv in data["per_vehicle"]:
                    print(f"  Vehicle {pv.get('vehicle_id')} ({pv.get('plate_number')}): {pv.get('package_count')} pkgs")
            if "plan_id" in data:
                print(f"  Plan ID: {data['plan_id']}")
            if "summary" in data:
                s = data["summary"]
                print(f"  Summary: {s.get('placed_packages')} placed, {s.get('failed_packages')} failed, {s.get('utilization')}% util")

            if not placements:
                print("  (empty)")
                continue
            print(f"  {'Name':<20s} {'PkgID':>5s} {'X':>8s} {'Y':>8s} {'Z':>6s} {'Rot':>4s} {'Seq':>4s}")
            print(f"  {'-'*65}")
            for pl in placements:
                name = pl.get("name") or pl.get("pkg_name") or pl.get("_name") or pl.get("package_name") or ""
                pid = pl.get("package_id") or pl.get("id") or ""
                x = pl.get("x", "")
                y = pl.get("y", "")
                z = pl.get("z", "")
                rot = pl.get("rotation", "")
                seq = pl.get("load_sequence", "")
                # For canvas rep 5
                if "canvas_x" in pl:
                    x = f"{pl.get('x_mm','')}->cvs{pl.get('canvas_x',''):.0f}"
                    y = f"{pl.get('y_mm','')}->cvs{pl.get('canvas_y',''):.0f}"
                print(f"  {str(name)[:20]:<20s} {str(pid):>5s} {str(x):>8s} {str(y):>8s} {str(z):>6s} {str(rot):>4s} {str(seq):>4s}")

            if "view" in data:
                print(f"  View: {data['view']}, Container dims: {data.get('container_mm', {})}")
            if "container_mm" in data:
                print(f"  Container: {data.get('container_mm', {})}")


def list_traces(traces):
    print("\nAvailable traces:")
    for tid in sorted(traces.keys()):
        reps = sorted(set(e["rep"] for e in traces[tid]))
        labels = sorted(set(e["label"] for e in traces[tid]))
        print(f"  {tid}: reps={reps}, labels={labels}")


if __name__ == "__main__":
    traces = load_traces()
    if not traces:
        exit(0)

    import sys
    if len(sys.argv) > 1:
        trace_id = sys.argv[1]
        if trace_id in traces:
            show_trace(trace_id, traces[trace_id])
        else:
            print(f"Trace {trace_id} not found")
            list_traces(traces)
    else:
        list_traces(traces)
        # Show the most recent trace
        last = sorted(traces.keys())[-1]
        print(f"\nShowing most recent trace: {last}")
        show_trace(last, traces[last])
