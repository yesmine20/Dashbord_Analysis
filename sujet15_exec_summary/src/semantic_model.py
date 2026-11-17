"""Extract, parse, and validate PBIP/TMDL semantic model metadata and DAX contracts."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import config


@dataclass
class MeasureMetadata:
    """Detailed definition of a DAX measure defined in TMDL."""
    table: str
    name: str
    expression: str
    description: str = ""
    format_string: str = ""
    display_folder: str = ""
    is_hidden: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{self.table}[{self.name}]"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ColumnMetadata:
    """Detailed definition of a column defined in TMDL."""
    table: str
    name: str
    data_type: str = ""
    description: str = ""
    format_string: str = ""
    source_column: str = ""
    is_hidden: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{self.table}[{self.name}]"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelationshipMetadata:
    """Model relationship defined in relationships.tmdl."""
    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    is_active: bool = True
    cardinality: str = "manyToOne"
    cross_filtering: str = "single"

    @property
    def summary(self) -> str:
        status = "Active" if self.is_active else "Inactive"
        return (
            f"{self.from_table}[{self.from_column}] -> "
            f"{self.to_table}[{self.to_column}] ({status})"
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TableMetadata:
    """Metadata of a table declared in a TMDL file."""
    name: str
    description: str = ""
    columns: dict[str, ColumnMetadata] = field(default_factory=dict)
    measures: dict[str, MeasureMetadata] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "columns": {k: v.as_dict() for k, v in self.columns.items()},
            "measures": {k: v.as_dict() for k, v in self.measures.items()},
        }


@dataclass
class SemanticModelCatalog:
    """Complete semantic model catalog loaded from PBIP/TMDL."""
    project: str
    definition_path: str
    tables: dict[str, TableMetadata] = field(default_factory=dict)
    relationships: list[RelationshipMetadata] = field(default_factory=list)

    @property
    def all_measures(self) -> dict[str, MeasureMetadata]:
        out: dict[str, MeasureMetadata] = {}
        for table in self.tables.values():
            for m in table.measures.values():
                out[m.qualified_name] = m
                if m.name not in out:
                    out[m.name] = m
        return out

    def get_measure(self, name: str) -> MeasureMetadata | None:
        """Find a measure by short name 'Profit' or qualified 'Sales[Profit]'."""
        cleaned = name.strip()
        if "[" in cleaned and cleaned.endswith("]"):
            table_part, col_part = cleaned.split("[", 1)
            table_part = table_part.strip(" '")
            col_part = col_part[:-1].strip(" '")
            key = f"{table_part}[{col_part}]"
            return self.all_measures.get(key)
        return self.all_measures.get(cleaned)

    def active_relationship_for(
        self, from_table: str, to_table: str
    ) -> RelationshipMetadata | None:
        """Find active relationship connecting two tables."""
        for rel in self.relationships:
            if (
                rel.is_active
                and rel.from_table.lower() == from_table.lower()
                and rel.to_table.lower() == to_table.lower()
            ):
                return rel
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "definition_path": self.definition_path,
            "tables": {k: v.as_dict() for k, v in self.tables.items()},
            "relationships": [r.as_dict() for r in self.relationships],
        }


# ================================================================
# TMDL PARSING FUNCTIONS
# ================================================================

def _strip_name(token: str) -> str:
    """Normalize TMDL object names ('Sales' -> Sales, 'Sales Order' -> Sales Order)."""
    token = token.strip()
    if token.startswith("'") and token.endswith("'"):
        token = token[1:-1].replace("''", "'")
    return token.strip()


def _parse_column_ref(s: str) -> tuple[str, str]:
    """Parse 'Sales Territory'.SalesTerritoryKey or Sales.OrderDateKey."""
    s = s.strip()
    match = re.match(r"^(?:'([^']+)'|([^.\s]+))\.(?:'([^']+)'|([^.\s]+))$", s)
    if match:
        table_name = match.group(1) or match.group(2)
        col_name = match.group(3) or match.group(4)
        return _strip_name(table_name), _strip_name(col_name)
    return "", s


def parse_table_tmdl(path: Path) -> TableMetadata:
    """Parse a single .tmdl table file into TableMetadata."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    table_name = path.stem
    table_desc_lines: list[str] = []
    
    table_meta = TableMetadata(name=table_name)

    current_item: dict[str, Any] | None = None
    item_type: str | None = None  # "column" | "measure"
    pending_doc: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Doc comment lines
        if stripped.startswith("///"):
            doc_text = stripped.lstrip("/").strip()
            if not current_item and not table_meta.description:
                table_desc_lines.append(doc_text)
            else:
                pending_doc.append(doc_text)
            continue

        # Top-level table header
        table_match = re.match(r"^table\s+('(?:[^']|'')+'|[^\s]+)", line)
        if table_match:
            table_meta.name = _strip_name(table_match.group(1))
            if table_desc_lines:
                table_meta.description = " ".join(table_desc_lines)
                table_desc_lines = []
            continue

        # Measure declaration: measure Name = Expression
        measure_match = re.match(
            r"^\tmeasure\s+('(?:[^']|'')+'|[^\s=]+)\s*=\s*(.*)", line
        )
        if measure_match:
            m_name = _strip_name(measure_match.group(1))
            expr = measure_match.group(2).strip()
            desc = " ".join(pending_doc) if pending_doc else ""
            pending_doc = []
            m_obj = MeasureMetadata(
                table=table_meta.name,
                name=m_name,
                expression=expr,
                description=desc,
            )
            table_meta.measures[m_name] = m_obj
            current_item = m_obj.as_dict()
            item_type = "measure"
            continue

        # Column declaration: column Name
        col_match = re.match(r"^\tcolumn\s+('(?:[^']|'')+'|[^\s]+)", line)
        if col_match:
            c_name = _strip_name(col_match.group(1))
            desc = " ".join(pending_doc) if pending_doc else ""
            pending_doc = []
            c_obj = ColumnMetadata(
                table=table_meta.name,
                name=c_name,
                description=desc,
            )
            table_meta.columns[c_name] = c_obj
            current_item = c_obj.as_dict()
            item_type = "column"
            continue

        # Indented properties under column or measure
        if current_item and item_type:
            target_obj = (
                table_meta.measures.get(current_item["name"])
                if item_type == "measure"
                else table_meta.columns.get(current_item["name"])
            )
            if target_obj is None:
                continue

            if stripped.startswith("formatString:"):
                raw_fmt = stripped.split(":", 1)[1].strip()
                target_obj.format_string = raw_fmt.strip('"')
            elif stripped.startswith("dataType:"):
                target_obj.data_type = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("displayFolder:"):
                target_obj.display_folder = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("sourceColumn:"):
                target_obj.source_column = stripped.split(":", 1)[1].strip()
            elif "isHidden" in stripped or "changedProperty = IsHidden" in stripped:
                target_obj.is_hidden = True

    return table_meta


def parse_relationships_tmdl(path: Path) -> list[RelationshipMetadata]:
    """Parse relationships.tmdl into a list of RelationshipMetadata objects."""
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=relationship\s+)", text.strip())
    results: list[RelationshipMetadata] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0]
        rel_id = header.split()[1] if len(header.split()) > 1 else ""

        props: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                props[k.strip()] = v.strip()

        from_t, from_c = _parse_column_ref(props.get("fromColumn", ""))
        to_t, to_c = _parse_column_ref(props.get("toColumn", ""))
        is_active = props.get("isActive", "true").lower() != "false"
        cardinality = props.get("fromCardinality", "manyToOne")
        cross_filtering = props.get("crossFilteringBehavior", "single")

        if from_t and to_t:
            results.append(
                RelationshipMetadata(
                    id=rel_id,
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    is_active=is_active,
                    cardinality=cardinality,
                    cross_filtering=cross_filtering,
                )
            )

    return results


# ================================================================
# MODEL CATALOG & CONTRACT VALIDATION
# ================================================================

_CATALOG_CACHE: SemanticModelCatalog | None = None


def get_model_catalog(
    model_dir: Path | None = None, reload: bool = False
) -> SemanticModelCatalog:
    """Load and cache the complete SemanticModelCatalog from PBIP definition files."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None and not reload:
        return _CATALOG_CACHE

    target_dir = model_dir or config.PBIP_MODEL_DIR
    tables_dir = target_dir / "tables"
    rel_file = target_dir / "relationships.tmdl"

    tables: dict[str, TableMetadata] = {}
    if tables_dir.is_dir():
        for tmdl_file in tables_dir.glob("*.tmdl"):
            table_meta = parse_table_tmdl(tmdl_file)
            tables[table_meta.name] = table_meta

    relationships = parse_relationships_tmdl(rel_file)

    catalog = SemanticModelCatalog(
        project=config.ROOT.name,
        definition_path=str(target_dir.relative_to(config.ROOT) if target_dir.is_relative_to(config.ROOT) else target_dir),
        tables=tables,
        relationships=relationships,
    )
    _CATALOG_CACHE = catalog
    return catalog


TABLE_FILES = {
    "Date": "Date.tmdl",
    "Product": "Product.tmdl",
    "Sales Territory": "Sales Territory.tmdl",
    "Sales Order": "Sales Order.tmdl",
    "Sales": "Sales.tmdl",
}

QUERY_CONTRACT = {
    "Date": {"Month"},
    "Product": {"Category"},
    "Sales Territory": {"Group"},
    "Sales Order": {"Channel"},
    "Sales": {"Sales", "Cost", "Profit", "Orders"},
}


def validate_query_contract() -> dict[str, Any]:
    """Ensure all DAX fields/measures used by the app still exist in TMDL.
    
    Returns an enriched contract dictionary compatible with app.py and tests.
    """
    catalog = get_model_catalog()

    missing: list[str] = []
    for table_name, required_fields in QUERY_CONTRACT.items():
        table_meta = catalog.tables.get(table_name)
        if not table_meta:
            missing.append(f"table '{table_name}'")
            continue

        available = set(table_meta.columns.keys()) | set(table_meta.measures.keys())
        for req in required_fields:
            if req not in available:
                missing.append(f"{table_name}[{req}]")

    if missing:
        raise RuntimeError(
            "The DAX query no longer matches the PBIP/TMDL model. Missing: "
            + ", ".join(missing)
        )

    # Active date relationship
    date_rel = catalog.active_relationship_for("Sales", "Date")
    date_basis_info = date_rel.summary if date_rel else "Direct date relationship"

    # Measures metadata enriched
    enriched_measures = {}
    for m_name in ("Sales", "Cost", "Profit", "Orders"):
        m = catalog.get_measure(m_name)
        if m:
            enriched_measures[m_name] = {
                "dax": m.expression,
                "description": m.description,
                "format": m.format_string,
            }

    return {
        "project": config.ROOT.name,
        "model_definition": catalog.definition_path,
        "dimensions": [
            "Date[Month]",
            "Product[Category]",
            "Sales Territory[Group]",
            "Sales Order[Channel]",
        ],
        "measures": [
            "Sales[Sales]",
            "Sales[Cost]",
            "Sales[Profit]",
            "Sales[Orders]",
        ],
        "date_relationship": date_basis_info,
        "measures_definition": enriched_measures,
    }


def get_semantic_context_for_prompt() -> str:
    """Format TMDL measures and relationships into concise Markdown for the LLM prompt."""
    catalog = get_model_catalog()
    lines = [
        "### Contexte Sémantique Certifié (Power BI TMDL / PBIP)",
        "Les indicateurs financiers proviennent exclusivement des mesures DAX officielles du modèle :",
    ]

    key_measures = ["Sales", "Cost", "Profit", "Profit %", "Orders"]
    for name in key_measures:
        m = catalog.get_measure(name)
        if m:
            desc = f" — {m.description}" if m.description else ""
            lines.append(f"- **{m.name}** : `{m.expression}`{desc}")

    date_rel = catalog.active_relationship_for("Sales", "Date")
    if date_rel:
        lines.append(
            f"- **Axe Temporel Actif** : `{date_rel.from_table}[{date_rel.from_column}] -> {date_rel.to_table}[{date_rel.to_column}]` (Date de commande / Order Date)."
        )

    lines.append(
        "- **Règle d'additivité** : La mesure `Orders` est un compte distinct (`DISTINCTCOUNT`) et n'est pas additive entre les lignes."
    )
    return "\n".join(lines)
