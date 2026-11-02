// BSD 3-Clause License
// Copyright (c) 2023, Stephen Fletcher
// Modifications copyright (c) 2026, Dicer Lab contributors.
// See LICENSE and THIRD_PARTY_NOTICES.md for redistribution terms.
package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"os"
	"sort"
	"strings"
)

const designSchemaVersion = 1

type occurrence struct {
	GeneID string `json:"gene_id"`
	Start  int    `json:"start"`
	End    int    `json:"end"`
}

type kmerRecord struct {
	ID           string       `json:"id"`
	SequenceRNA  string       `json:"sequence_rna"`
	Occurrences  []occurrence `json:"occurrences"`
	GeneCount    int          `json:"occurrences_count"`
	ExcludedRefs []string     `json:"excluded_reference_ids"`
}

type discoveryResult struct {
	SchemaVersion           int          `json:"schema_version"`
	K                       int          `json:"k"`
	Genes                   []string     `json:"genes"`
	Kmers                   []kmerRecord `json:"kmers"`
	FilteredKmers           []kmerRecord `json:"filtered_kmers"`
	ReferenceWindowsSkipped int          `json:"reference_windows_skipped"`
}

type assembleRequest struct {
	SchemaVersion int                `json:"schema_version"`
	Lambda        int                `json:"lambda"`
	Weights       map[string]float64 `json:"weights"`
}

type assembleResult struct {
	SchemaVersion    int     `json:"schema_version"`
	SelectedSequence string  `json:"selected_sequence_rna"`
	Coverage         int     `json:"coverage"`
	Weight           float64 `json:"weight"`
	Objective        float64 `json:"objective"`
	DeterministicTie bool    `json:"deterministic_tie_break"`
}

type blockTarget struct {
	GeneID      string `json:"gene_id"`
	SequenceDNA string `json:"sequence_dna"`
}

type blockLength struct {
	GeneID   string `json:"gene_id"`
	LengthNT int    `json:"length_nt"`
}

type blocksRequest struct {
	SchemaVersion    int                `json:"schema_version"`
	Targets          []blockTarget      `json:"targets"`
	BlockLengths     []blockLength      `json:"block_lengths"`
	Weights          map[string]float64 `json:"weights"`
	MaxBlocksPerGene int                `json:"max_blocks_per_gene"`
}

type blockCandidate struct {
	GeneID        string   `json:"gene_id"`
	Start         int      `json:"start"`
	End           int      `json:"end"`
	SequenceRNA   string   `json:"sequence_rna"`
	Score         float64  `json:"score"`
	KmerSequences []string `json:"kmer_sequences"`
}

type geneBlocks struct {
	GeneID string           `json:"gene_id"`
	Blocks []blockCandidate `json:"blocks"`
}

type blocksResult struct {
	SchemaVersion int          `json:"schema_version"`
	Blocks        []geneBlocks `json:"blocks"`
}

type screenRequest struct {
	SchemaVersion int `json:"schema_version"`
	Candidates    []struct {
		ID          string `json:"id"`
		SequenceDNA string `json:"sequence_dna"`
	} `json:"candidates"`
}

type offTargetHit struct {
	CandidateID  string   `json:"candidate_id"`
	Start        int      `json:"start"`
	End          int      `json:"end"`
	SequenceRNA  string   `json:"sequence_rna"`
	ReferenceIDs []string `json:"reference_ids"`
}

type screenResult struct {
	SchemaVersion           int            `json:"schema_version"`
	Hits                    []offTargetHit `json:"hits"`
	ReferenceWindowsSkipped int            `json:"reference_windows_skipped"`
}

type stringFlag []string

func (f *stringFlag) String() string         { return strings.Join(*f, ",") }
func (f *stringFlag) Set(value string) error { *f = append(*f, value); return nil }

func designProtocolMain(args []string) error {
	switch args[0] {
	case "discover":
		return discoverProtocol(args[1:])
	case "assemble":
		return assembleProtocol(args[1:])
	case "blocks":
		return blocksProtocol(args[1:])
	case "screen":
		return screenProtocol(args[1:])
	default:
		return errors.New("unknown protocol mode")
	}
}

func discoverProtocol(args []string) error {
	flags := flag.NewFlagSet("discover", flag.ContinueOnError)
	targetsPath := flags.String("targets", "", "target FASTA file")
	k := flags.Int("k", 21, "target k-mer length")
	var offTargets stringFlag
	flags.Var(&offTargets, "offtargets", "off-target FASTA; repeat once per reference")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *targetsPath == "" || *k != 21 || flags.NArg() != 0 {
		return errors.New("discover requires --targets and --k 21")
	}
	refs, err := readDesignFASTA(*targetsPath)
	if err != nil {
		return err
	}
	if len(refs) == 0 {
		return errors.New("target FASTA contains no sequences")
	}
	for _, ref := range refs {
		if len(ref.Seq) < *k {
			return fmt.Errorf("target %q is shorter than k=%d", ref.Header, *k)
		}
	}

	genes := make([]string, len(refs))
	for i, ref := range refs {
		genes[i] = ref.Header
	}
	// Reuse dsRNAmax's original unique-kmer/presence algorithm. Coordinates are
	// added in the adapter because the upstream routine intentionally stores only
	// a per-target presence vector.
	unique := getKmers(refs, *k)
	sequences := make([]string, 0, len(unique))
	for sequence := range unique {
		sequences = append(sequences, sequence)
	}
	sort.Strings(sequences)
	orientationLookup := make(map[string][]string, len(sequences)*2)
	for _, sequence := range sequences {
		orientationLookup[sequence] = append(orientationLookup[sequence], sequence)
		reverse := reverseComplement(sequence)
		if reverse != sequence {
			orientationLookup[reverse] = append(orientationLookup[reverse], sequence)
		}
	}
	result := discoveryResult{SchemaVersion: designSchemaVersion, K: *k, Genes: genes,
		Kmers: make([]kmerRecord, 0), FilteredKmers: make([]kmerRecord, 0)}
	filteredBySequence := make(map[string]map[string]struct{})
	for _, path := range offTargets {
		skipped, err := walkReferenceWindows(path, *k, func(refID string, start int, window string) error {
			for _, sequence := range orientationLookup[window] {
				if filteredBySequence[sequence] == nil {
					filteredBySequence[sequence] = make(map[string]struct{})
				}
				filteredBySequence[sequence][refID] = struct{}{}
			}
			return nil
		})
		if err != nil {
			return fmt.Errorf("read off-target reference %q: %w", path, err)
		}
		result.ReferenceWindowsSkipped += skipped
	}
	for _, sequence := range sequences {
		rec := kmerRecord{
			SequenceRNA:  strings.ReplaceAll(sequence, "T", "U"),
			Occurrences:  make([]occurrence, 0),
			ExcludedRefs: make([]string, 0),
		}
		hash := sha256.Sum256([]byte(rec.SequenceRNA))
		rec.ID = hex.EncodeToString(hash[:])
		for _, ref := range refs {
			for start := 0; start+*k <= len(ref.Seq); start++ {
				if ref.Seq[start:start+*k] == sequence {
					rec.Occurrences = append(rec.Occurrences, occurrence{GeneID: ref.Header, Start: start, End: start + *k})
				}
			}
		}
		if len(rec.Occurrences) == 0 {
			return fmt.Errorf("dsRNAmax presence vector disagrees with occurrence scan for %s", sequence)
		}
		for _, present := range unique[sequence] {
			if present != 0 {
				rec.GeneCount++
			}
		}
		if refs, excluded := filteredBySequence[sequence]; excluded {
			for id := range refs {
				rec.ExcludedRefs = append(rec.ExcludedRefs, id)
			}
			sort.Strings(rec.ExcludedRefs)
			result.FilteredKmers = append(result.FilteredKmers, rec)
		} else {
			result.Kmers = append(result.Kmers, rec)
		}
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}

func blocksProtocol(args []string) error {
	flags := flag.NewFlagSet("blocks", flag.ContinueOnError)
	requestPath := flags.String("request", "", "JSON block assembly request")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *requestPath == "" || flags.NArg() != 0 {
		return errors.New("blocks requires --request")
	}
	var request blocksRequest
	if err := readJSON(*requestPath, &request); err != nil {
		return err
	}
	if request.SchemaVersion != designSchemaVersion || request.MaxBlocksPerGene != 5 || len(request.Targets) == 0 || len(request.Targets) > 8 || len(request.BlockLengths) != len(request.Targets) {
		return errors.New("invalid block request: schema=1, up to 8 targets, one length each, max_blocks_per_gene=5 required")
	}
	lengths := make(map[string]int, len(request.BlockLengths))
	for _, item := range request.BlockLengths {
		if item.GeneID == "" || item.LengthNT < 21 || item.LengthNT > 1000 {
			return fmt.Errorf("invalid block length for gene %q", item.GeneID)
		}
		if _, found := lengths[item.GeneID]; found {
			return fmt.Errorf("duplicate block length for %q", item.GeneID)
		}
		lengths[item.GeneID] = item.LengthNT
	}
	if len(request.Weights) == 0 {
		return errors.New("no eligible target k-mers")
	}
	result := blocksResult{SchemaVersion: designSchemaVersion, Blocks: make([]geneBlocks, 0, len(request.Targets))}
	seenGenes := make(map[string]struct{})
	for _, target := range request.Targets {
		length, found := lengths[target.GeneID]
		if target.GeneID == "" || !found || len(target.SequenceDNA) < length {
			return fmt.Errorf("missing length or insufficient target sequence for %q", target.GeneID)
		}
		if _, found := seenGenes[target.GeneID]; found {
			return fmt.Errorf("duplicate target gene %q", target.GeneID)
		}
		seenGenes[target.GeneID] = struct{}{}
		if _, found := request.Weights["unexpected"]; found {
			return errors.New("invalid k-mer weight key")
		}
		gene := geneBlocks{GeneID: target.GeneID, Blocks: make([]blockCandidate, 0, 5)}
		bySequence := make(map[string]blockCandidate)
		for start := 0; start+length <= len(target.SequenceDNA); start++ {
			sequence := strings.ToUpper(target.SequenceDNA[start : start+length])
			if !isUnambiguousDNA(sequence) {
				return fmt.Errorf("target %q contains non-ACGT sequence", target.GeneID)
			}
			uniqueKmers := make(map[string]struct{})
			eligible := true
			for offset := 0; offset+21 <= len(sequence); offset++ {
				kmer := strings.ReplaceAll(sequence[offset:offset+21], "T", "U")
				weight, ok := request.Weights[kmer]
				if !ok {
					eligible = false
					break
				}
				if !finite(weight) || weight < 1 || weight > 2 {
					return fmt.Errorf("invalid weight for k-mer %s", kmer)
				}
				uniqueKmers[kmer] = struct{}{}
			}
			if !eligible {
				continue
			}
			kmerSequences := make([]string, 0, len(uniqueKmers))
			score := 0.0
			for kmer := range uniqueKmers {
				kmerSequences = append(kmerSequences, kmer)
				score += request.Weights[kmer]
			}
			sort.Strings(kmerSequences)
			candidate := blockCandidate{GeneID: target.GeneID, Start: start, End: start + length,
				SequenceRNA: strings.ReplaceAll(sequence, "T", "U"), Score: score, KmerSequences: kmerSequences}
			existing, duplicate := bySequence[candidate.SequenceRNA]
			if !duplicate || candidate.Score > existing.Score || (candidate.Score == existing.Score && candidate.Start < existing.Start) {
				bySequence[candidate.SequenceRNA] = candidate
			}
		}
		for _, candidate := range bySequence {
			gene.Blocks = append(gene.Blocks, candidate)
		}
		sort.Slice(gene.Blocks, func(i, j int) bool {
			if gene.Blocks[i].Score != gene.Blocks[j].Score {
				return gene.Blocks[i].Score > gene.Blocks[j].Score
			}
			if gene.Blocks[i].SequenceRNA != gene.Blocks[j].SequenceRNA {
				return gene.Blocks[i].SequenceRNA < gene.Blocks[j].SequenceRNA
			}
			return gene.Blocks[i].Start < gene.Blocks[j].Start
		})
		if len(gene.Blocks) > 5 {
			gene.Blocks = gene.Blocks[:5]
		}
		if len(gene.Blocks) == 0 {
			return fmt.Errorf("no_feasible_block for gene %q", target.GeneID)
		}
		result.Blocks = append(result.Blocks, gene)
	}
	if len(seenGenes) != len(lengths) {
		return errors.New("block lengths must cover every target exactly once")
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}

func screenProtocol(args []string) error {
	flags := flag.NewFlagSet("screen", flag.ContinueOnError)
	requestPath := flags.String("request", "", "JSON candidate request")
	var offTargets stringFlag
	flags.Var(&offTargets, "offtargets", "off-target FASTA; repeat once per reference")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *requestPath == "" || len(offTargets) == 0 || flags.NArg() != 0 {
		return errors.New("screen requires --request and at least one --offtargets")
	}
	var request screenRequest
	if err := readJSON(*requestPath, &request); err != nil {
		return err
	}
	if request.SchemaVersion != designSchemaVersion || len(request.Candidates) == 0 {
		return errors.New("invalid screen request")
	}
	type position struct {
		candidate string
		start     int
		end       int
		window    string
	}
	type hitKey struct {
		candidate string
		start     int
	}
	lookup := make(map[string][]position)
	positions := make([]position, 0)
	for _, candidate := range request.Candidates {
		if candidate.ID == "" || len(candidate.SequenceDNA) < 21 || !isUnambiguousDNA(candidate.SequenceDNA) {
			return fmt.Errorf("invalid candidate %q", candidate.ID)
		}
		for start := 0; start+21 <= len(candidate.SequenceDNA); start++ {
			window := candidate.SequenceDNA[start : start+21]
			item := position{candidate: candidate.ID, start: start, end: start + 21, window: window}
			positions = append(positions, item)
			lookup[window] = append(lookup[window], item)
			reverse := reverseComplement(window)
			if reverse != window {
				lookup[reverse] = append(lookup[reverse], item)
			}
		}
	}
	foundRefs := make(map[hitKey]map[string]struct{})
	skipped := 0
	for _, path := range offTargets {
		count, err := walkReferenceWindows(path, 21, func(refID string, start int, window string) error {
			for _, item := range lookup[window] {
				key := hitKey{candidate: item.candidate, start: item.start}
				if foundRefs[key] == nil {
					foundRefs[key] = make(map[string]struct{})
				}
				foundRefs[key][refID] = struct{}{}
			}
			return nil
		})
		if err != nil {
			return err
		}
		skipped += count
	}
	result := screenResult{SchemaVersion: designSchemaVersion, Hits: make([]offTargetHit, 0), ReferenceWindowsSkipped: skipped}
	for _, item := range positions {
		ids := foundRefs[hitKey{candidate: item.candidate, start: item.start}]
		if len(ids) == 0 {
			continue
		}
		refIDs := make([]string, 0, len(ids))
		for id := range ids {
			refIDs = append(refIDs, id)
		}
		sort.Strings(refIDs)
		result.Hits = append(result.Hits, offTargetHit{CandidateID: item.candidate, Start: item.start, End: item.end,
			SequenceRNA: strings.ReplaceAll(item.window, "T", "U"), ReferenceIDs: refIDs})
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}

func assembleProtocol(args []string) error {
	flags := flag.NewFlagSet("assemble", flag.ContinueOnError)
	kmersPath := flags.String("kmers", "", "versioned k-mer JSON")
	requestPath := flags.String("request", "", "versioned weighted-assembly JSON")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *kmersPath == "" || *requestPath == "" || flags.NArg() != 0 {
		return errors.New("assemble requires --kmers and --request")
	}
	var discovered discoveryResult
	if err := readJSON(*kmersPath, &discovered); err != nil {
		return fmt.Errorf("read k-mers: %w", err)
	}
	var request assembleRequest
	if err := readJSON(*requestPath, &request); err != nil {
		return fmt.Errorf("read request: %w", err)
	}
	if discovered.SchemaVersion != designSchemaVersion || discovered.K != 21 || request.SchemaVersion != designSchemaVersion {
		return errors.New("unsupported design protocol schema or k")
	}
	if request.Lambda != 0 && request.Lambda != 1 {
		return errors.New("lambda must be 0 or 1")
	}
	if len(request.Weights) != len(discovered.Kmers) {
		return errors.New("weight set must contain every discovered k-mer exactly once")
	}
	best := assembleResult{SchemaVersion: designSchemaVersion, DeterministicTie: true}
	hasBest := false
	for _, record := range discovered.Kmers {
		weight, ok := request.Weights[record.SequenceRNA]
		if !ok || !finite(weight) || weight < 1 || weight > 2 {
			return fmt.Errorf("missing or invalid weight for k-mer %s", record.SequenceRNA)
		}
		coverage := record.GeneCount
		objective := float64(coverage) * weight
		if !hasBest || objective > best.Objective || (objective == best.Objective && record.SequenceRNA < best.SelectedSequence) {
			best.SelectedSequence = record.SequenceRNA
			best.Coverage = coverage
			best.Weight = weight
			best.Objective = objective
			hasBest = true
		}
	}
	if !hasBest {
		return errors.New("no candidate k-mers")
	}
	return json.NewEncoder(os.Stdout).Encode(best)
}

func readDesignFASTA(path string) ([]*HeaderRef, error) {
	return readFASTA(path, false)
}

func walkReferenceWindows(path string, k int, visit func(referenceID string, start int, window string) error) (int, error) {
	skipped := 0
	count, err := walkFASTA(path, true, func(ref *HeaderRef) error {
		refID, _, found := strings.Cut(ref.Header, "|")
		if !found || refID == "" {
			return fmt.Errorf("reference header %q must start with reference ID and |", ref.Header)
		}
		localSkipped, windowErr := forEachUnambiguousWindow(ref.Seq, k, func(start int, window string) error {
			return visit(refID, start, window)
		})
		skipped += localSkipped
		return windowErr
	})
	if err != nil {
		return skipped, err
	}
	if count == 0 {
		return skipped, io.EOF
	}
	return skipped, nil
}

func forEachUnambiguousWindow(sequence string, k int, visit func(start int, window string) error) (int, error) {
	if k < 1 {
		return 0, errors.New("k must be positive")
	}
	invalid := 0
	skipped := 0
	for end := 0; end < len(sequence); end++ {
		if !isCanonicalDNA(sequence[end]) {
			invalid++
		}
		if end >= k && !isCanonicalDNA(sequence[end-k]) {
			invalid--
		}
		if end+1 < k {
			continue
		}
		start := end + 1 - k
		if invalid > 0 {
			skipped++
			continue
		}
		if err := visit(start, sequence[start:end+1]); err != nil {
			return skipped, err
		}
	}
	return skipped, nil
}

func isCanonicalDNA(base byte) bool {
	return base == 'A' || base == 'C' || base == 'G' || base == 'T'
}

func readFASTA(path string, allowAmbiguous bool) ([]*HeaderRef, error) {
	var refs []*HeaderRef
	_, err := walkFASTA(path, allowAmbiguous, func(ref *HeaderRef) error {
		ref.ReverseSeq = reverseComplement(ref.Seq)
		refs = append(refs, ref)
		return nil
	})
	return refs, err
}

func walkFASTA(path string, allowAmbiguous bool, visit func(*HeaderRef) error) (int, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, fmt.Errorf("open FASTA: %w", err)
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64*1024), 2*1024*1024)
	seenHeaders := make(map[string]struct{})
	var header string
	var sequence strings.Builder
	count := 0
	flush := func() error {
		if header == "" {
			if sequence.Len() == 0 {
				return nil
			}
			return errors.New("sequence before first FASTA header")
		}
		seq := strings.ToUpper(sequence.String())
		if len(seq) == 0 {
			return fmt.Errorf("empty target %q", header)
		}
		for _, base := range seq {
			if !strings.ContainsRune("ACGT", base) && (!allowAmbiguous || !strings.ContainsRune("ACGTRYSWKMBDHVN", base)) {
				return fmt.Errorf("sequence %q contains unsupported base %q", header, base)
			}
		}
		if _, exists := seenHeaders[header]; exists {
			return fmt.Errorf("duplicate FASTA header %q", header)
		}
		seenHeaders[header] = struct{}{}
		if err := visit(&HeaderRef{Header: header, Seq: seq}); err != nil {
			return err
		}
		count++
		sequence.Reset()
		return nil
	}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, ">") {
			if err := flush(); err != nil {
				return count, err
			}
			header = strings.TrimSpace(strings.TrimPrefix(line, ">"))
			if header == "" {
				return count, errors.New("empty FASTA header")
			}
			continue
		}
		sequence.WriteString(line)
	}
	if err := scanner.Err(); err != nil {
		return count, fmt.Errorf("read FASTA: %w", err)
	}
	if err := flush(); err != nil {
		return count, err
	}
	if count == 0 {
		return 0, io.EOF
	}
	return count, nil
}

func isUnambiguousDNA(sequence string) bool {
	for _, base := range sequence {
		if !strings.ContainsRune("ACGT", base) {
			return false
		}
	}
	return true
}

func readJSON(path string, target any) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()
	decoder := json.NewDecoder(file)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return errors.New("unexpected trailing JSON value")
		}
		return err
	}
	return nil
}

func finite(value float64) bool { return !math.IsNaN(value) && !math.IsInf(value, 0) }
