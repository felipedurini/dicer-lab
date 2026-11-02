"""Clasificación determinista de productos simulados."""

from dataclasses import dataclass

from .domain import Construct, MoleculeResult, Product


@dataclass(frozen=True)
class ProductAnnotation:
    """Fases de entrada y eventos de alineación de un producto."""

    relative_phase_before: int
    relative_phase_after: int
    global_phase_before: int
    aligned21_local: bool
    aligned21_global: bool
    contained_segment_id: str | None = None
    touching_segment_ids: tuple[str, ...] = ()
    crossed_boundaries: tuple[int, ...] = ()
    overlap_nt_by_segment: tuple[tuple[str, int], ...] = ()
    crossed_gene_boundaries: tuple[int, ...] = ()

    @property
    def crossed_segment_boundaries(self) -> tuple[int, ...]:
        """Alias explícito; crossed_boundaries conserva la API histórica."""
        return self.crossed_boundaries


@dataclass(frozen=True)
class OrdinalCount:
    """Conteos por ordinal; `n_reached` distingue probabilidad conjunta y condicional."""

    cut_index: int
    n_reached: int
    relative_phase_before_count: int
    relative_phase_after_count: int
    aligned21_local_count: int


@dataclass(frozen=True)
class SegmentCount:
    """Métricas de productos por tramo objetivo."""

    segment_id: str
    gene_id: str
    start: int
    end: int
    n_molecules: int
    contained_count: int
    touching_count: int
    crossing_touching_count: int
    overlap_nt: int

    @property
    def containment_fraction(self) -> float | None:
        return _ratio(self.contained_count, self.touching_count)

    @property
    def crossing_fraction(self) -> float | None:
        return _ratio(self.crossing_touching_count, self.touching_count)

    @property
    def segment_crossing_fraction(self) -> float | None:
        return self.crossing_fraction

    @property
    def coverage_fraction(self) -> float | None:
        return _ratio(self.overlap_nt, self.n_molecules * (self.end - self.start))


@dataclass(frozen=True)
class GeneCount:
    """Productos y solapamiento por gen; cruce de segmento y de gen separados."""

    gene_id: str
    segment_ids: tuple[str, ...]
    gene_length_nt: int
    n_molecules: int
    contained_count: int
    touching_count: int
    crossing_touching_count: int
    overlap_nt: int
    gene_crossing_touching_count: int = 0

    @property
    def containment_fraction(self) -> float | None:
        return _ratio(self.contained_count, self.touching_count)

    @property
    def crossing_fraction(self) -> float | None:
        return _ratio(self.crossing_touching_count, self.touching_count)

    @property
    def segment_crossing_fraction(self) -> float | None:
        return self.crossing_fraction

    @property
    def gene_crossing_fraction(self) -> float | None:
        return _ratio(self.gene_crossing_touching_count, self.touching_count)

    @property
    def coverage_fraction(self) -> float | None:
        return _ratio(self.overlap_nt, self.n_molecules * self.gene_length_nt)


@dataclass(frozen=True)
class PhysicalUnitCount:
    """Recuperación exacta de una celda completa de la retícula global."""

    start: int
    end: int
    recovered_molecule_count: int
    n_molecules: int

    @property
    def recovery_fraction(self) -> float | None:
        return _ratio(self.recovered_molecule_count, self.n_molecules)


@dataclass(frozen=True)
class DirectionSummary:
    """Métricas direccionales; crossing_count sigue contando fronteras de segmento."""

    direction: str
    n_molecules: int
    n_molecules_without_products: int
    n_products: int
    length_counts: tuple[tuple[int, int], ...]
    relative_phase_before_count: int
    relative_phase_after_count: int
    global_phase_before_count: int
    aligned21_local_count: int
    aligned21_global_count: int
    contained_count: int
    crossing_count: int
    terminal_length_items: tuple[tuple[int, int], ...]
    terminal_reason_items: tuple[tuple[str, int], ...]
    ordinal_counts: tuple[OrdinalCount, ...]
    gene_crossing_count: int = 0

    @property
    def proportion21(self) -> float | None:
        return _ratio(dict(self.length_counts)[21], self.n_products)

    @property
    def terminal_length_counts(self) -> dict[int, int]:
        return dict(self.terminal_length_items)

    @property
    def terminal_reason_counts(self) -> dict[str, int]:
        return dict(self.terminal_reason_items)

    @property
    def segment_crossing_count(self) -> int:
        """Conteo histórico de productos que cruzan cualquier frontera de segmento."""
        return self.crossing_count

    @property
    def segment_crossing_fraction(self) -> float | None:
        return _ratio(self.crossing_count, self.n_products)

    @property
    def gene_crossing_fraction(self) -> float | None:
        return _ratio(self.gene_crossing_count, self.n_products)


@dataclass(frozen=True)
class CountSummary:
    """Conteos agrupados con cruces de segmento y de gen separados."""

    n_molecules: int
    n_molecules_without_products: int
    n_products: int
    length_counts: tuple[tuple[int, int], ...]
    relative_phase_before_count: int
    relative_phase_after_count: int
    global_phase_before_count: int
    aligned21_local_count: int
    aligned21_global_count: int
    contained_count: int
    crossing_count: int
    terminal_length_items: tuple[tuple[int, int], ...]
    terminal_reason_items: tuple[tuple[str, int], ...]
    ordinal_counts: tuple[OrdinalCount, ...]
    segment_counts: tuple[SegmentCount, ...]
    gene_counts: tuple[GeneCount, ...]
    physical_unit_counts: tuple[PhysicalUnitCount, ...]
    direction_summaries: tuple[DirectionSummary, ...] = ()
    gene_crossing_count: int = 0

    @property
    def proportion21_numerator(self) -> int:
        return dict(self.length_counts)[21]

    @property
    def proportion21_denominator(self) -> int:
        return self.n_products

    @property
    def proportion21(self) -> float | None:
        return _ratio(self.proportion21_numerator, self.proportion21_denominator)

    @property
    def proportion_by_length(self) -> tuple[tuple[int, int, int, float | None], ...]:
        return tuple(
            (length, count, self.n_products, _ratio(count, self.n_products))
            for length, count in self.length_counts
        )

    @property
    def terminal_length_counts(self) -> dict[int, int]:
        return dict(self.terminal_length_items)

    @property
    def terminal_reason_counts(self) -> dict[str, int]:
        return dict(self.terminal_reason_items)

    @property
    def segment_crossing_count(self) -> int:
        """Alias explícito; crossing_count conserva el cruce de segmento histórico."""
        return self.crossing_count

    @property
    def segment_crossing_fraction(self) -> float | None:
        return _ratio(self.crossing_count, self.n_products)

    @property
    def gene_crossing_fraction(self) -> float | None:
        return _ratio(self.gene_crossing_count, self.n_products)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def classify_product(
    product: Product,
    construct: Construct,
    direction: str,
) -> ProductAnnotation:
    """Calcula el registro local y global sin inferir actividad biológica."""
    if not isinstance(product, Product):
        raise TypeError("product debe ser Product")
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")
    if direction not in ("left", "right"):
        raise ValueError("direction debe ser 'left' o 'right'")

    length = product.length_nt
    if product.end > construct.length_nt:
        raise ValueError("el producto excede la longitud del constructo")
    if product.remaining_before > construct.length_nt:
        raise ValueError("remaining_before excede la longitud del constructo")

    consumed = construct.length_nt - product.remaining_before
    if direction == "left":
        if product.start != consumed or product.end != consumed + length:
            raise ValueError("las coordenadas no corresponden al estado desde la izquierda")
        entry_coordinate = product.start
    else:
        if product.end != product.remaining_before:
            raise ValueError("las coordenadas no corresponden al estado desde la derecha")
        entry_coordinate = product.end

    relative_before = consumed % 21
    relative_after = (consumed + length) % 21
    global_before = (entry_coordinate - construct.phase_origin_nt) % 21
    touching: list[str] = []
    overlaps: list[tuple[str, int]] = []
    contained_segment_id: str | None = None
    for segment in construct.segments:
        overlap = max(0, min(product.end, segment.end) - max(product.start, segment.start))
        if overlap:
            touching.append(segment.segment_id)
            overlaps.append((segment.segment_id, overlap))
            if product.start >= segment.start and product.end <= segment.end:
                contained_segment_id = segment.segment_id

    boundaries = tuple(
        segment.end
        for segment in construct.segments[:-1]
        if product.start < segment.end < product.end
    )
    gene_boundaries = tuple(
        left.end
        for left, right in zip(construct.segments, construct.segments[1:])
        if left.gene_id != right.gene_id and product.start < left.end < product.end
    )

    return ProductAnnotation(
        relative_phase_before=relative_before,
        relative_phase_after=relative_after,
        global_phase_before=global_before,
        aligned21_local=length == 21 and relative_before == 0,
        aligned21_global=(
            length == 21
            and (product.start - construct.phase_origin_nt) % 21 == 0
        ),
        contained_segment_id=contained_segment_id,
        touching_segment_ids=tuple(touching),
        crossed_boundaries=boundaries,
        overlap_nt_by_segment=tuple(overlaps),
        crossed_gene_boundaries=gene_boundaries,
    )


def summarize(results, construct: Construct) -> CountSummary:
    """Resume resultados en una pasada, sin tratar productos como réplicas independientes."""
    if not isinstance(construct, Construct):
        raise TypeError("construct debe ser Construct")

    n_molecules = 0
    n_without_products = 0
    n_products = 0
    length_counts = {21: 0, 22: 0, 24: 0}
    relative_before = relative_after = global_before = 0
    aligned_local = aligned_global = contained = crossing = gene_crossing = 0
    terminal_lengths = {length: 0 for length in range(24)}
    terminal_reasons = {
        "exhausted": 0,
        "shorter_than_min": 0,
        "proposal_exceeds_remaining": 0,
    }
    direction_accumulator = {
        direction: {
            "n_molecules": 0,
            "n_without_products": 0,
            "n_products": 0,
            "length_counts": {21: 0, 22: 0, 24: 0},
            "relative_before": 0,
            "relative_after": 0,
            "global_before": 0,
            "aligned_local": 0,
            "aligned_global": 0,
            "contained": 0,
            "crossing": 0,
            "gene_crossing": 0,
            "terminal_lengths": {length: 0 for length in range(24)},
            "terminal_reasons": {
                "exhausted": 0,
                "shorter_than_min": 0,
                "proposal_exceeds_remaining": 0,
            },
            "ordinal": [],
        }
        for direction in ("left", "right")
    }
    ordinal_accumulator: list[list[int]] = []
    segment_accumulator = {
        segment.segment_id: [0, 0, 0, 0] for segment in construct.segments
    }
    genes_in_order = tuple(dict.fromkeys(segment.gene_id for segment in construct.segments))
    gene_segments = {
        gene_id: tuple(segment for segment in construct.segments if segment.gene_id == gene_id)
        for gene_id in genes_in_order
    }
    gene_accumulator = {gene_id: [0, 0, 0, 0, 0] for gene_id in genes_in_order}
    physical_units = tuple(
        (start, start + 21)
        for start in range(construct.phase_origin_nt, construct.length_nt - 20, 21)
        if start + 21 <= construct.length_nt
    )
    physical_recovery = {interval: 0 for interval in physical_units}

    for result in results:
        if not isinstance(result, MoleculeResult):
            raise TypeError("cada resultado debe ser MoleculeResult")
        n_molecules += 1
        directional = direction_accumulator[result.direction]
        directional["n_molecules"] += 1
        if not result.products:
            n_without_products += 1
            directional["n_without_products"] += 1
        emitted = sum(product.length_nt for product in result.products)
        if emitted + result.remainder.length_nt != construct.length_nt:
            raise ValueError("los productos y el remanente no conservan la longitud inicial")

        expected_remaining = construct.length_nt
        molecule_recovered_units: set[tuple[int, int]] = set()
        for product in result.products:
            if product.remaining_before != expected_remaining:
                raise ValueError("los productos no siguen una trayectoria contigua")
            annotation = classify_product(product, construct, result.direction)
            length_counts[product.length_nt] += 1
            n_products += 1
            directional["length_counts"][product.length_nt] += 1
            directional["n_products"] += 1
            relative_before += annotation.relative_phase_before == 0
            relative_after += annotation.relative_phase_after == 0
            global_before += annotation.global_phase_before == 0
            aligned_local += annotation.aligned21_local
            aligned_global += annotation.aligned21_global
            directional["relative_before"] += annotation.relative_phase_before == 0
            directional["relative_after"] += annotation.relative_phase_after == 0
            directional["global_before"] += annotation.global_phase_before == 0
            directional["aligned_local"] += annotation.aligned21_local
            directional["aligned_global"] += annotation.aligned21_global
            if annotation.contained_segment_id is not None:
                contained += 1
                directional["contained"] += 1
            elif annotation.crossed_boundaries:
                crossing += 1
                directional["crossing"] += 1
            else:
                raise ValueError("un producto debe estar contenido en un tramo o cruzar una juntura")
            if annotation.crossed_gene_boundaries:
                gene_crossing += 1
                directional["gene_crossing"] += 1

            overlap_by_segment = dict(annotation.overlap_nt_by_segment)
            touched_ids = set(annotation.touching_segment_ids)
            crossed_segment_ids = {
                segment.segment_id
                for segment in construct.segments
                if any(
                    product.start < boundary < product.end
                    for boundary in (segment.start, segment.end)
                    if boundary not in (0, construct.length_nt)
                )
            }
            touched_genes: set[str] = set()
            crossing_genes: set[str] = set()
            gene_crossing_genes: set[str] = set()
            overlap_by_gene: dict[str, int] = {}
            for segment in construct.segments:
                segment_id = segment.segment_id
                accumulator = segment_accumulator[segment_id]
                overlap = overlap_by_segment.get(segment_id, 0)
                if overlap:
                    accumulator[1] += 1
                    accumulator[3] += overlap
                    touched_genes.add(segment.gene_id)
                    overlap_by_gene[segment.gene_id] = (
                        overlap_by_gene.get(segment.gene_id, 0) + overlap
                    )
                if annotation.contained_segment_id == segment_id:
                    accumulator[0] += 1
                if segment_id in crossed_segment_ids:
                    accumulator[2] += 1
                    crossing_genes.add(segment.gene_id)

            for left, right in zip(construct.segments, construct.segments[1:]):
                if left.end in annotation.crossed_gene_boundaries:
                    gene_crossing_genes.add(left.gene_id)
                    gene_crossing_genes.add(right.gene_id)

            for gene_id in touched_genes:
                gene_accumulator[gene_id][1] += 1
            for gene_id in crossing_genes:
                gene_accumulator[gene_id][2] += 1
            for gene_id in gene_crossing_genes:
                gene_accumulator[gene_id][4] += 1
            for gene_id, overlap in overlap_by_gene.items():
                gene_accumulator[gene_id][3] += overlap
            if annotation.contained_segment_id is not None:
                contained_gene = next(
                    segment.gene_id
                    for segment in construct.segments
                    if segment.segment_id == annotation.contained_segment_id
                )
                gene_accumulator[contained_gene][0] += 1

            interval = (product.start, product.end)
            if interval in physical_recovery:
                molecule_recovered_units.add(interval)

            while len(ordinal_accumulator) < product.cut_index:
                ordinal_accumulator.append([0, 0, 0, 0])
            ordinal = ordinal_accumulator[product.cut_index - 1]
            ordinal[0] += 1
            ordinal[1] += annotation.relative_phase_before == 0
            ordinal[2] += annotation.relative_phase_after == 0
            ordinal[3] += annotation.aligned21_local
            while len(directional["ordinal"]) < product.cut_index:
                directional["ordinal"].append([0, 0, 0, 0])
            directional_ordinal = directional["ordinal"][product.cut_index - 1]
            directional_ordinal[0] += 1
            directional_ordinal[1] += annotation.relative_phase_before == 0
            directional_ordinal[2] += annotation.relative_phase_after == 0
            directional_ordinal[3] += annotation.aligned21_local
            expected_remaining -= product.length_nt

        if result.remainder.length_nt != expected_remaining:
            raise ValueError("la longitud del remanente no sigue al último producto")
        if result.direction == "left":
            expected_coordinates = (emitted, construct.length_nt)
            if result.remainder.reason == "exhausted":
                expected_coordinates = (construct.length_nt, construct.length_nt)
        else:
            expected_coordinates = (0, result.remainder.length_nt)
        if (result.remainder.start, result.remainder.end) != expected_coordinates:
            raise ValueError("las coordenadas del remanente no corresponden a la dirección")

        terminal_lengths[result.remainder.length_nt] += 1
        terminal_reasons[result.remainder.reason] += 1
        directional["terminal_lengths"][result.remainder.length_nt] += 1
        directional["terminal_reasons"][result.remainder.reason] += 1
        for interval in molecule_recovered_units:
            physical_recovery[interval] += 1

    ordinal_counts = tuple(
        OrdinalCount(index, *counts)
        for index, counts in enumerate(ordinal_accumulator, start=1)
    )
    segment_counts = tuple(
        SegmentCount(
            segment.segment_id,
            segment.gene_id,
            segment.start,
            segment.end,
            n_molecules,
            *segment_accumulator[segment.segment_id],
        )
        for segment in construct.segments
    )
    gene_counts = tuple(
        GeneCount(
            gene_id,
            tuple(segment.segment_id for segment in gene_segments[gene_id]),
            sum(segment.end - segment.start for segment in gene_segments[gene_id]),
            n_molecules,
            *gene_accumulator[gene_id],
        )
        for gene_id in genes_in_order
    )
    physical_unit_counts = tuple(
        PhysicalUnitCount(start, end, physical_recovery[(start, end)], n_molecules)
        for start, end in physical_units
    )
    direction_summaries = tuple(
        DirectionSummary(
            direction=direction,
            n_molecules=state["n_molecules"],
            n_molecules_without_products=state["n_without_products"],
            n_products=state["n_products"],
            length_counts=tuple((length, state["length_counts"][length]) for length in (21, 22, 24)),
            relative_phase_before_count=state["relative_before"],
            relative_phase_after_count=state["relative_after"],
            global_phase_before_count=state["global_before"],
            aligned21_local_count=state["aligned_local"],
            aligned21_global_count=state["aligned_global"],
            contained_count=state["contained"],
            crossing_count=state["crossing"],
            terminal_length_items=tuple(state["terminal_lengths"].items()),
            terminal_reason_items=tuple(state["terminal_reasons"].items()),
            ordinal_counts=tuple(
                OrdinalCount(index, *counts)
                for index, counts in enumerate(state["ordinal"], start=1)
            ),
            gene_crossing_count=state["gene_crossing"],
        )
        for direction, state in direction_accumulator.items()
    )
    return CountSummary(
        n_molecules=n_molecules,
        n_molecules_without_products=n_without_products,
        n_products=n_products,
        length_counts=tuple((length, length_counts[length]) for length in (21, 22, 24)),
        relative_phase_before_count=relative_before,
        relative_phase_after_count=relative_after,
        global_phase_before_count=global_before,
        aligned21_local_count=aligned_local,
        aligned21_global_count=aligned_global,
        contained_count=contained,
        crossing_count=crossing,
        terminal_length_items=tuple(terminal_lengths.items()),
        terminal_reason_items=tuple(terminal_reasons.items()),
        ordinal_counts=ordinal_counts,
        segment_counts=segment_counts,
        gene_counts=gene_counts,
        physical_unit_counts=physical_unit_counts,
        direction_summaries=direction_summaries,
        gene_crossing_count=gene_crossing,
    )


def _merge_ordinal_counts(groups) -> tuple[OrdinalCount, ...]:
    max_length = max((len(group) for group in groups), default=0)
    merged = []
    for index in range(max_length):
        counts = [
            (group[index].n_reached,
             group[index].relative_phase_before_count,
             group[index].relative_phase_after_count,
             group[index].aligned21_local_count)
            if index < len(group)
            else (0, 0, 0, 0)
            for group in groups
        ]
        merged.append(OrdinalCount(index + 1, *(sum(item[i] for item in counts) for i in range(4))))
    return tuple(merged)


def _merge_direction_summaries(groups: tuple[DirectionSummary, ...]) -> DirectionSummary:
    if not groups or any(group.direction != groups[0].direction for group in groups):
        raise ValueError("los subgrupos de dirección a combinar deben coincidir")
    first = groups[0]
    return DirectionSummary(
        direction=first.direction,
        n_molecules=sum(group.n_molecules for group in groups),
        n_molecules_without_products=sum(group.n_molecules_without_products for group in groups),
        n_products=sum(group.n_products for group in groups),
        length_counts=tuple(
            (length, sum(dict(group.length_counts)[length] for group in groups))
            for length, _ in first.length_counts
        ),
        relative_phase_before_count=sum(group.relative_phase_before_count for group in groups),
        relative_phase_after_count=sum(group.relative_phase_after_count for group in groups),
        global_phase_before_count=sum(group.global_phase_before_count for group in groups),
        aligned21_local_count=sum(group.aligned21_local_count for group in groups),
        aligned21_global_count=sum(group.aligned21_global_count for group in groups),
        contained_count=sum(group.contained_count for group in groups),
        crossing_count=sum(group.crossing_count for group in groups),
        terminal_length_items=tuple(
            (length, sum(group.terminal_length_counts[length] for group in groups))
            for length, _ in first.terminal_length_items
        ),
        terminal_reason_items=tuple(
            (reason, sum(group.terminal_reason_counts[reason] for group in groups))
            for reason, _ in first.terminal_reason_items
        ),
        ordinal_counts=_merge_ordinal_counts(tuple(group.ordinal_counts for group in groups)),
        gene_crossing_count=sum(group.gene_crossing_count for group in groups),
    )


def merge_summaries(summaries) -> CountSummary:
    """Combina resúmenes del mismo constructo sin perder denominadores."""
    summaries = tuple(summaries)
    if not summaries:
        raise ValueError("se requiere al menos un resumen para combinar")
    if any(not isinstance(summary, CountSummary) for summary in summaries):
        raise TypeError("todos los elementos deben ser CountSummary")

    first = summaries[0]
    for summary in summaries[1:]:
        if tuple((item.segment_id, item.gene_id, item.start, item.end) for item in summary.segment_counts) != tuple(
            (item.segment_id, item.gene_id, item.start, item.end) for item in first.segment_counts
        ):
            raise ValueError("los resúmenes deben tener la misma partición de tramos")
        if tuple((item.start, item.end) for item in summary.physical_unit_counts) != tuple(
            (item.start, item.end) for item in first.physical_unit_counts
        ):
            raise ValueError("los resúmenes deben tener las mismas unidades físicas")
        if tuple(item.gene_id for item in summary.gene_counts) != tuple(
            item.gene_id for item in first.gene_counts
        ):
            raise ValueError("los resúmenes deben tener los mismos genes")

    directions = []
    first_by_direction = {item.direction: item for item in first.direction_summaries}
    for direction in first_by_direction:
        matching = []
        for summary in summaries:
            directional = {item.direction: item for item in summary.direction_summaries}
            if set(directional) != set(first_by_direction):
                raise ValueError("los resúmenes deben cubrir los mismos subgrupos de dirección")
            matching.append(directional[direction])
        directions.append(_merge_direction_summaries(tuple(matching)))

    return CountSummary(
        n_molecules=sum(summary.n_molecules for summary in summaries),
        n_molecules_without_products=sum(summary.n_molecules_without_products for summary in summaries),
        n_products=sum(summary.n_products for summary in summaries),
        length_counts=tuple(
            (length, sum(dict(summary.length_counts)[length] for summary in summaries))
            for length, _ in first.length_counts
        ),
        relative_phase_before_count=sum(summary.relative_phase_before_count for summary in summaries),
        relative_phase_after_count=sum(summary.relative_phase_after_count for summary in summaries),
        global_phase_before_count=sum(summary.global_phase_before_count for summary in summaries),
        aligned21_local_count=sum(summary.aligned21_local_count for summary in summaries),
        aligned21_global_count=sum(summary.aligned21_global_count for summary in summaries),
        contained_count=sum(summary.contained_count for summary in summaries),
        crossing_count=sum(summary.crossing_count for summary in summaries),
        terminal_length_items=tuple(
            (length, sum(summary.terminal_length_counts[length] for summary in summaries))
            for length, _ in first.terminal_length_items
        ),
        terminal_reason_items=tuple(
            (reason, sum(summary.terminal_reason_counts[reason] for summary in summaries))
            for reason, _ in first.terminal_reason_items
        ),
        ordinal_counts=_merge_ordinal_counts(tuple(summary.ordinal_counts for summary in summaries)),
        segment_counts=tuple(
            SegmentCount(
                template.segment_id, template.gene_id, template.start, template.end,
                sum(summary.segment_counts[index].n_molecules for summary in summaries),
                sum(summary.segment_counts[index].contained_count for summary in summaries),
                sum(summary.segment_counts[index].touching_count for summary in summaries),
                sum(summary.segment_counts[index].crossing_touching_count for summary in summaries),
                sum(summary.segment_counts[index].overlap_nt for summary in summaries),
            )
            for index, template in enumerate(first.segment_counts)
        ),
        gene_counts=tuple(
            GeneCount(
                template.gene_id, template.segment_ids, template.gene_length_nt,
                sum(summary.gene_counts[index].n_molecules for summary in summaries),
                sum(summary.gene_counts[index].contained_count for summary in summaries),
                sum(summary.gene_counts[index].touching_count for summary in summaries),
                sum(summary.gene_counts[index].crossing_touching_count for summary in summaries),
                sum(summary.gene_counts[index].overlap_nt for summary in summaries),
                sum(summary.gene_counts[index].gene_crossing_touching_count for summary in summaries),
            )
            for index, template in enumerate(first.gene_counts)
        ),
        physical_unit_counts=tuple(
            PhysicalUnitCount(
                template.start, template.end,
                sum(summary.physical_unit_counts[index].recovered_molecule_count for summary in summaries),
                sum(summary.physical_unit_counts[index].n_molecules for summary in summaries),
            )
            for index, template in enumerate(first.physical_unit_counts)
        ),
        direction_summaries=tuple(directions),
        gene_crossing_count=sum(summary.gene_crossing_count for summary in summaries),
    )
