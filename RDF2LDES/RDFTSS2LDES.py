from rdflib import Graph,URIRef,Namespace,BNode,Literal,Dataset
from rdflib.namespace import XSD,RDF
from rdflib.term import BNode
import pandas as pd
import argparse
from collections import defaultdict
from datetime import datetime, timezone,timedelta
import json
import os
import calendar
import time
from pathlib import Path
from dateutil.relativedelta import relativedelta
from datetime import timezone
import json


directory = "./ldes-output"
AS = Namespace("https://www.w3.org/ns/activitystreams#")
LDES = Namespace("https://w3id.org/ldes#")
TREE = Namespace("https://w3id.org/tree#")
TSS = Namespace("https://w3id.org/tss#")
eventstream_uri = URIRef("https://example.org/ldes/stream#eventstream")
base_uri = URIRef("https://example.org/ldes/stream/")
home_page = URIRef("https://example.org/ldes/stream/stream.trig")
input_path = "timeseries.ttl"
base_path = "./ldes-output"


def set_property(
    property_name,
    directory_input="./ldes-output",
    base_path_input="./ldes-output",
    base_uri_input="https://example.org/ldes/",
):
    """Configure one LDES generation run without a domain-specific public URL."""
    global directory, eventstream_uri, home_page, base_path, base_uri
    directory = str(directory_input)
    base_path = str(base_path_input)
    public_root = str(base_uri_input).rstrip("/")
    stream_root = f"{public_root}/{property_name}"
    base_uri = URIRef(f"{stream_root}/")
    eventstream_uri = URIRef(f"{stream_root}#eventstream")
    home_page = URIRef(f"{stream_root}/{property_name}.trig")

# split the data into their designated folders
def load_graph(input_path):
    g = Graph()
    g.parse(input_path, format="turtle", publicID="https://example.org/")
    return g

def process_graph(graph):
    query = """
PREFIX tss: <https://w3id.org/tss#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?snippet ?fromTime ?toTime ?pointType ?pointsJson
       ?template ?sensor ?observedProperty
WHERE {
    ?snippet a tss:Snippet ;
             tss:about ?template ;
             tss:from ?fromTime ;
             tss:until ?toTime ;
             tss:pointType ?pointType ;
             tss:points ?pointsJson .

    ?template a tss:PointTemplate ;
              sosa:madeBySensor ?sensor ;
              sosa:observedProperty ?observedProperty .
}
"""
    result = graph.query(query)
    print(f"Total snippets processed: {len(result)}")
    return result

def divide_data(result):
    SOSA = Namespace("http://www.w3.org/ns/sosa/")
    EX   = Namespace("http://example.org/")
    TSS  = Namespace("https://w3id.org/tss#")

    # group by (sensor, property, date) — one entry per day per sensor
    grouped = defaultdict(lambda: {"rows": [], "points": []})

    for row in result:
        points_raw = str(row["pointsJson"])
        try:
            points = json.loads(points_raw)
        except json.JSONDecodeError:
            points = []

        # split individual point records by their own date
        daily_points = defaultdict(list)
        for pt in points:
            pt_dt = datetime.fromisoformat(pt["time"]).astimezone(timezone.utc)
            day_key = (pt_dt.year, pt_dt.month, pt_dt.day)
            daily_points[day_key].append(pt)

        for day_key, day_pts in daily_points.items():
            grouped[day_key]["rows"].append(row)
            grouped[day_key]["points"].append((row, day_pts))

    for (year, month, day), data in grouped.items():

        ds = Dataset()
        ds.bind("sosa", SOSA)
        ds.bind("ex",   EX)
        ds.bind("tss",  TSS)
        ds.bind("xsd",  XSD)
        ds.bind("ldes", LDES)
        ds.bind("tree", TREE)
        ds.bind("as",   AS)

        metadata_graph = ds.default_context
        metadata_graph.add((eventstream_uri, RDF.type,          LDES.EventStream))
        metadata_graph.add((eventstream_uri, LDES.timestampPath, TSS["from"]))
        metadata_graph.add((eventstream_uri, TREE.view,          home_page))

        day_start = datetime(year, month, day,  0,  0,  0, tzinfo=timezone.utc)
        day_end   = datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc)

        for row, day_pts in data["points"]:
            snippet_iri      = row["snippet"]
            sensor           = row["sensor"]
            observedProperty = row["observedProperty"]

            # scope the BNode and snippet IRI to this specific day
            day_suffix     = f"{year:04d}{month:02d}{day:02d}"
            day_snippet_iri = URIRef(str(snippet_iri) + f"/{day_suffix}")
            #template_bnode  = BNode(value=str(snippet_iri) + f"_template_{day_suffix}")
            template_bnode  = BNode()
            g_snip = ds.graph(day_snippet_iri)

            g_snip.add((day_snippet_iri, RDF.type,       TSS.Snippet))
            g_snip.add((day_snippet_iri, TSS.about,      template_bnode))
            g_snip.add((day_snippet_iri, TSS["from"],    Literal(day_start, datatype=XSD.dateTime)))
            g_snip.add((day_snippet_iri, TSS["until"],   Literal(day_end,   datatype=XSD.dateTime)))
            g_snip.add((day_snippet_iri, TSS.pointType,  Literal(row["pointType"])))
            # only the points belonging to this day
            g_snip.add((day_snippet_iri, TSS.points,     Literal(json.dumps(day_pts, indent=1), datatype=RDF.JSON)))

            g_snip.add((template_bnode, RDF.type,                TSS.PointTemplate))
            g_snip.add((template_bnode, SOSA.madeBySensor,       sensor))
            g_snip.add((template_bnode, SOSA.observedProperty,   observedProperty))

            metadata_graph.add((eventstream_uri, TREE.member,  day_snippet_iri))
            metadata_graph.add((day_snippet_iri, TSS["from"],  Literal(day_start, datatype=XSD.dateTime)))

        file_path = os.path.join(
            base_path,
            f"{year:04d}", f"{month:02d}", f"{day:02d}",
            "readings.trig"
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        ds.serialize(destination=file_path, format="trig")

#################################################################################################################################

#  Add the LDES metadata files
def delete_ldes_files():
    for root, dirs, files in os.walk(directory):
        if(Path(os.path.join(root, f"{Path(root).parts[-1]}.trig"))).exists():
            os.remove(os.path.join(root, f"{Path(root).parts[-1]}.trig"))

def create_ldes_files():
    # Anchor depth once so all relative checks are stable regardless of ../
    directory_path = Path(directory).resolve()
    # How many leading components to strip from local path before building URIs
    # e.g. "../LDESTSS" → skip ".." → URI starts at "LDESTSS/..."
    for root, dirs, files in os.walk(directory):
        path = Path(root).resolve()
        root = path.as_posix()

        # depth 0 = ../LDESTSS  (root index)
        # depth 1 = ../LDESTSS/2021  (year index)
        # depth 2 = ../LDESTSS/2021/03  (month index)
        # depth 3 = ../LDESTSS/2021/03/03  (leaf — has readings.trig, skip)
        relative_root = path.relative_to(directory_path)
        depth = 0 if relative_root == Path(".") else len(relative_root.parts)

        write_log(f"Current folder: {root} (depth={depth})\n")

        # leaf folders have no subfolders to index
        if not dirs or depth >= 3:
            continue

        # URI-safe relative root: strips leading ".." components
        uri_rel = "" if relative_root == Path(".") else relative_root.as_posix()

        temp_graph = create_base_graph()

        for d in dirs:
            temp_graph.add((eventstream_uri, TREE.view, home_page))
            write_log(f"  Subfolder: {d}\n")

            bn_ge = BNode()
            bn_lt = BNode()

            # the index file this folder will write
            index_uri = home_page if depth == 0 else URIRef(f"{base_uri}{uri_rel}/{path.parts[-1]}.trig")
            temp_graph.add((index_uri, TREE.relation, bn_ge))
            temp_graph.add((index_uri, TREE.relation, bn_lt))

            temp_graph.add((bn_ge, RDF.type, TREE.GreaterThanOrEqualToRelation))
            temp_graph.add((bn_ge, TREE.path, TSS["from"]))
            temp_graph.add((bn_lt, RDF.type, TREE.LessThanRelation))
            temp_graph.add((bn_lt, TREE.path, TSS["from"]))

            # child node URIs: year/month folders get a named index file,
            # day folders already have readings.trig
            child_root = f"{uri_rel}/{d}" if uri_rel else d
            if depth <= 1:
                child_uri = URIRef(f"{base_uri}{child_root}/{d}.trig")
            else:  # depth == 2, month → day
                child_uri = URIRef(f"{base_uri}{child_root}/readings.trig")

            temp_graph.add((bn_ge, TREE.node, child_uri))
            temp_graph.add((bn_lt, TREE.node, child_uri))

            # datetime bounds depend on what level d represents
            if depth == 0:                          # d is a year
                ge_dt = datetime(int(d), 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                lt_dt = datetime(int(d) + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            elif depth == 1:                        # d is a month, parent is year
                year = int(path.parts[-1])
                ge_dt = datetime(year, int(d), 1, 0, 0, 0, tzinfo=timezone.utc)
                lt_dt = ge_dt + relativedelta(months=1)
            else:                                   # d is a day, parent is month
                year  = int(path.parts[-2])
                month = int(path.parts[-1])
                ge_dt = datetime(year, month, int(d), 0, 0, 0, tzinfo=timezone.utc)
                lt_dt = ge_dt + relativedelta(days=1)

            temp_graph.add((bn_ge, TREE.value, Literal(ge_dt, datatype=XSD.dateTime)))
            temp_graph.add((bn_lt, TREE.value, Literal(lt_dt, datatype=XSD.dateTime)))

        # write the index file for this folder
        index_file = os.path.join(root, f"{path.parts[-1]}.trig")
        write_log(f"Writing to: {index_file}\n")
        with open(index_file, "a") as f:
            f.write(temp_graph.serialize(format="trig"))

        write_log("-" * 40 + "\n")

def create_base_graph():
    g = Dataset()     # not Graph()
    default = g.default_context

    default.bind("as", AS)
    default.bind("ldes", LDES)
    default.bind("tree", TREE)
    default.bind("xsd", XSD)
    default.bind("tss",TSS)

    retention_bn = BNode()

    default.add((eventstream_uri, RDF.type, LDES.EventStream))
    #default.add((eventstream_uri, LDES.retentionPolicy, retention_bn))
    default.add((eventstream_uri, LDES.timestampPath, TSS["from"]))
    #default.add((eventstream_uri, LDES.versionCreateObject, AS.Create))
    #default.add((eventstream_uri, LDES.versionDeleteObject, AS.Delete))
    #default.add((eventstream_uri, LDES.versionOfPath, AS.object))

    #default.add((retention_bn, RDF.type, LDES.LatestVersionSubset))
    #default.add((retention_bn, LDES.amount, Literal(1, datatype=XSD.integer)))

    return g   # return the CG

def write_log(msg):
    log_path = Path(directory) / "generation.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(msg)

def delete_log():
    log_path = Path(directory) / "generation.log"
    if log_path.exists():
        log_path.unlink()


def generate_ldes(source_ttl, output_directory, stream_name, base_url="https://example.org/ldes/"):
    """Generate the existing TREE/LDES folder structure for one isolated run."""
    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    set_property(stream_name, output_directory, output_directory, base_url)
    original_graph = load_graph(str(source_ttl))
    result = process_graph(original_graph)
    divide_data(result)
    delete_log()
    delete_ldes_files()
    create_ldes_files()
    return sorted(output_directory.rglob("*.trig"))

#################################################################################################################################

def main():
######################################################################
    #I need to make a delete all folders function
    print("Starting processing...")
    start_time = time.perf_counter()
    original_graph = load_graph(input_path)
    result = process_graph(original_graph)
    divide_data(result)
    end_time = time.perf_counter()
    print(f"Processing completed in {end_time - start_time:.2f} seconds.")
######################################################################
    start_time = time.perf_counter()
    delete_log()
    delete_ldes_files()
    create_ldes_files()
    end_time = time.perf_counter()
    print(f"Processing completed in {end_time - start_time:.2f} seconds.")
######################################################################

if __name__ == "__main__":
    main()
