package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadDesignFASTARejectsAmbiguousAndDuplicateTargets(t *testing.T) {
	for name, data := range map[string]string{
		"ambiguous": ">g1\nACGTNACGT\n",
		"duplicate": ">g1\nACGT\n>g1\nACGT\n",
		"no_header": "ACGT\n",
	} {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "targets.fa")
			if err := os.WriteFile(path, []byte(data), 0o600); err != nil {
				t.Fatal(err)
			}
			if _, err := readDesignFASTA(path); err == nil {
				t.Fatal("expected invalid FASTA to be rejected")
			}
		})
	}
}
