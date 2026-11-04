from flask import Flask, render_template, request, redirect, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, cast, Integer
from urllib.parse import urlencode
from typing import Optional
from collections import defaultdict
import os
import re
import json

app = Flask(__name__, instance_relative_config=True)

db_path = os.path.join(app.instance_path, "plateletweb_central.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class BasicInfo(db.Model):
    __tablename__ = "genes"

    # composite primary key: (Gene Symbol, Species)
    gene_symbol = db.Column("Gene Symbol", db.String(50), primary_key=True)
    species = db.Column("Species", db.String(100), primary_key=True)

    gene_description = db.Column("Gene Description", db.Text)

    neighbourdegree = db.Column("Neighbourdegree", db.Integer)
    rpkm_value = db.Column("RPKM Value", db.Float)
    rpkm_delta = db.Column("RPKM delta", db.Float)
    detection_protein = db.Column("Detection on Protein Level?", db.String(50))
    is_nonortholog = db.Column("Is a Nonortholog?", db.String(50))
    molecule_type = db.Column("Type of Molecule", db.String(100))

    def __repr__(self):
        return f"<BasicInfo {self.gene_symbol} ({self.species})>"


class Interaction(db.Model):
    __tablename__ = "interactions"

    # composite primary key for ORM purposes
    gene_symbol_1 = db.Column("Gene Symbol 1", db.String(50), primary_key=True)
    gene_symbol_2 = db.Column("Gene Symbol 2", db.String(50), primary_key=True)
    species = db.Column("Species", db.String(100), primary_key=True)

    predicted_score = db.Column("Predicted Interaction Score", db.Float)
    is_in_central_cascade = db.Column("Is in Central Cascade?", db.Integer)

    def __repr__(self):
        return (
            f"<Interaction {self.gene_symbol_1} - {self.gene_symbol_2} "
            f"({self.species})>"
        )

# input sanitization regex

SYMBOL_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")

def sanitize_gene_symbol(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    s = s.upper()  # common for gene symbols; remove if you don’t want this

    # Hard fail on unexpected characters/length
    if not SYMBOL_RE.fullmatch(s):
        abort(400, description="Invalid gene symbol.")
    return s

# app startpoint
@app.route("/", methods=["GET", "POST"])
def index():
    gene_symbol_query = None
    selected_species = []

    # list of dicts:
    # {"basic_info": BasicInfo, "interaction_count": int, "interactions": [Interaction]}
    results = []

    # Species dropdown (from basic_info)
    species_options = [
        row[0]
        for row in (
            db.session.query(BasicInfo.species)
            .distinct()
            .order_by(BasicInfo.species.asc())
            .all()
        )
        if row[0] is not None
    ]
    species_set = set(species_options)

    # get user input
    if request.method == "POST":
        gene_symbol_query = sanitize_gene_symbol(request.form.get("gene_symbol"))

        raw_species = request.form.getlist("species_filter")
        selected_species = [s for s in raw_species if s in species_set]

        if gene_symbol_query:
            # find all matching basic_info rows for this gene symbol
            q = BasicInfo.query.filter(
                BasicInfo.gene_symbol.ilike(gene_symbol_query)
            )

            # if user picked a species, restrict to that species
            if selected_species:
                q = q.filter(BasicInfo.species.in_(selected_species))

            basic_info_records = q.all()

            for record in basic_info_records:
                inter_q = Interaction.query.filter(
                    Interaction.species == record.species,
                    or_(
                        Interaction.gene_symbol_1 == record.gene_symbol,
                        Interaction.gene_symbol_2 == record.gene_symbol,
                    ),
                )

                interactions = inter_q.all()
                interaction_count = len(interactions)

                # collecting interacting partner gene symbols
                partner_symbols = set()
                for inter in interactions:
                    if inter.gene_symbol_1 == record.gene_symbol:
                        partner_symbols.add(inter.gene_symbol_2)
                    elif inter.gene_symbol_2 == record.gene_symbol:
                        partner_symbols.add(inter.gene_symbol_1)

                # basic info for each intereacting partner gene
                partner_basic_infos = []
                if partner_symbols:
                    partner_basic_infos = (
                        db.session.query(BasicInfo)
                        .filter(
                            BasicInfo.species == record.species,
                            BasicInfo.gene_symbol.in_(partner_symbols),
                        )
                        .all()
                    )

                # creating gene-symbo, -> BasicInfo mapping for easy access in template
                partner_info_by_symbol = {
                    b.gene_symbol: b for b in partner_basic_infos
                }    
                                                
                # Build network data
                node_ids = set()
                central_nodes = set()
                edges = []

                for inter in interactions:
                    node_ids.add(inter.gene_symbol_1)
                    node_ids.add(inter.gene_symbol_2)
                    edges.append({
                        "data": {
                            "id": f"{inter.gene_symbol_1}-{inter.gene_symbol_2}",
                            "source": inter.gene_symbol_1,
                            "target": inter.gene_symbol_2,
                            "score": inter.predicted_score,
                            "is_central": inter.is_in_central_cascade,
                        }
                    })

                # building node data for cytoscape
                nodes = []
                for gene in node_ids:
                    # inline logic for molecule_type
                    if gene == record.gene_symbol:
                        molecule_type = getattr(record, "molecule_type", None)
                    else:
                        partner = partner_info_by_symbol.get(gene)
                        molecule_type = getattr(partner, "molecule_type", None) if partner else None

                    nodes.append({
                        "data": {
                            "id": gene,
                            "label": gene,
                            "molecule_type": molecule_type,
                        }
                    })

                network_elements = nodes + edges

                results.append(
                    {
                        "basic_info": record,
                        "interaction_count": interaction_count,
                        "interactions": interactions,
                        "partner_info": partner_info_by_symbol,
                        "network_elements": json.dumps(network_elements),
                    }
                )


    return render_template(
        "index.html",
        gene_symbol_query=gene_symbol_query,
        species_options=species_options,
        selected_species=selected_species,
        results=results,
    )

# central cascade visualization

@app.get("/central-cascade/<species>")
def central_cascade_page(species):
    # species is whatever string you store, e.g. "H. sapiens"
    return render_template("central_cascade.html", species=species)


@app.get("/api/central-cascade/<species>")
def central_cascade_data(species):
    cascade_int = cast(Interaction.is_in_central_cascade, Integer)

    interactions = (
        db.session.query(Interaction)
        .filter(
            Interaction.species == species,
            cascade_int > 0,  # only central cascade edges
        )
        .all()
    )

    node_ids = set()
    edges = []

    for inter in interactions:
        g1, g2 = inter.gene_symbol_1, inter.gene_symbol_2
        node_ids.add(g1); node_ids.add(g2)

        edges.append({
            "data": {
                "id": "--".join(sorted([g1, g2])),
                "source": g1,
                "target": g2,
                "score": inter.predicted_score or 0.0,
                "is_central": int(inter.is_in_central_cascade),  # 1 or 2
            }
        })

    # ---- molecule_type lookup (same idea as your initial code) ----
    basic_rows = (
        db.session.query(BasicInfo.gene_symbol, BasicInfo.molecule_type)
        .filter(BasicInfo.species == species, BasicInfo.gene_symbol.in_(node_ids))
        .all()
    )
    molecule_type_by_symbol = {gs: mt for gs, mt in basic_rows}

    nodes = []
    for g in sorted(node_ids):
        nodes.append({
            "data": {
                "id": g,
                "label": g,
                "molecule_type": molecule_type_by_symbol.get(g, "unknown"),
            }
        })

    return jsonify(nodes + edges)


# @app.route("/central-cascade-human")
# def central_cascade_human():



@app.route("/legacy-search", methods=["GET", "POST"])
def legacy_search():
    q = sanitize_gene_symbol(request.values.get("legacy"))  # str|None -> str|None
    if not q:
        return redirect("/")

    query = urlencode({"SearchTerm": q, "content": "proteins"})
    return redirect(f"/php/plateletweb.php?{query}", code=302)

@app.route("/network-extraction")
def network_extraction():
    query = urlencode({"content": "subnetworkextraction"})
    return redirect(f"/php/plateletweb.php?{query}", code=302)

@app.route("/advanced-search")
def advanced_search():
    query = urlencode({"content": "advancedsearch"})
    return redirect(f"/php/plateletweb.php?{query}", code=302)


@app.route("/publications")
def publications():
    # No context variables are needed for publications.html
    return render_template("publications.html")

@app.route("/tutorial")
def tutorial():
    # No context variables are needed for publications.html
    return render_template("tutorial.html")

@app.route("/contact")
def contact():
    # No context variables are needed for publications.html
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)
