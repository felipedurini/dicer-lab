# Third-party notices

Reviewed on 2026-11-02. The root MIT license applies to the project's own
licensable work; it does not replace the terms of dependencies, scientific
datasets, or upstream files. See [docs/LICENSING.md](docs/LICENSING.md) for
evidence, scope and the distinction between source and binary
distribution. This notice does not imply endorsement by upstream authors.

| Component | Included / used | Terms and attribution |
| --- | --- | --- |
| dsRNAmax | Vendored source, tests and fixtures; local modifications | BSD-3-Clause; copyright 2023 Stephen Fletcher. Preserve [original license](vendor/dsrnamax/LICENSE) and [modification record](vendor/dsrnamax/THIRD_PARTY_NOTICES.md). Cite Fletcher et al. (2025), doi:10.1093/nargab/lqaf064. |
| strutil 0.2.3 | Go dependency linked into dsRNAmax | MIT; Adrian-George Bostan. [License](vendor/licenses/strutil-MIT.txt). |
| tablewriter 0.0.5 | Go dependency linked into dsRNAmax | MIT; Oleku Konko. [License](vendor/licenses/tablewriter-MIT.txt). |
| go-runewidth 0.0.9 | Transitive Go dependency | MIT; Yasuhiro Matsumoto. [License](vendor/licenses/go-runewidth-MIT.txt). |
| Go runtime | Compiled into the Go executable | Go Authors, BSD-3-Clause. [License](vendor/licenses/Go-BSD-3-Clause.txt); the Docker build also retains the build toolchain's actual notice. |
| ViennaRNA 2.7.2 | Installed Python/native dependency, not vendored source | Custom license, **not MIT**. [COPYING](vendor/licenses/ViennaRNA-2.7.2-COPYING.txt), [AUTHORS](vendor/licenses/ViennaRNA-2.7.2-AUTHORS.txt). Credit the authors and Institute for Theoretical Chemistry, University of Vienna. Cite Lorenz et al. (2011), doi:10.1186/1748-7188-6-26. |
| NAVIEW in ViennaRNA | Upstream plotting component; Dicer Lab does not invoke plotting | Robert E. Bruccoleri, 1988. Copying is permitted for noncommercial purposes with credit and notice; other copying requires permission. [Separate notice](vendor/licenses/ViennaRNA-2.7.2-naview-notice.txt). Review inclusion in any distributed wheel/image. |
| LUCID / sifi21_plus | Reference conventions; pipeline/source not shipped | Revision `37910bd6744b2ce6ce4c9b2582819b130e7ea509`. Conflicting GPLv3 LICENSE and MIT package metadata. No MIT permission is inferred. Local parameter provenance is established separately below. |
| Zuber 2022 thermodynamic data | 21 pairs of numeric parameters, Tables 1–2, New Model columns | Copyright The Author(s) 2022. Jeffrey Zuber, Susan J. Schroeder, Hongying Sun, Douglas H. Turner and David H. Mathews; doi:10.1093/nar/gkac261. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Adapted subset, notation and strand order; uncertainties omitted; combined with two Biopython entries. [Full mapping, source and changes](docs/RNA_NN4_PROVENANCE.md). |
| Biopython 1.86 RNA_NN3 data | Two pairs, CT/GA and GA/CT; no runtime dependency | BSD-3-Clause option, [license](vendor/licenses/Biopython-1.86-LICENSE.txt). Copyright 1999–2024 The Biopython Contributors, 2004–2008 Sebastian Bassi, 2013–2018 Markus Piotrowski. Scientific source: Chen et al. (2012), doi:10.1021/bi3002709, Table 3 parenthesized values. [Attribution and evidence](docs/RNA_NN4_PROVENANCE.md). |
| NCBI RefSeq | Bundled Apis mellifera transcript FASTA and optional runtime imports | [Dataset notice](services/simulator_api/reference_data/NOTICE.md). NCBI places no restriction of its own on molecular data, but does not transfer or clear submitters' rights. Not relicensed under MIT. |
| Python / JavaScript packages | Restored by pip/npm from manifests and locks | [Inventory](docs/licenses/dependencies.csv). Preserve package copyright and license files when distributing installed software; additional bundled native libraries can have separate terms. |
| Next.js scaffold | Framework-generated starting files, favicon and public template assets | MIT; Vercel, Inc. [License](vendor/licenses/Next-MIT.txt). Logos are not an endorsement of Dicer Lab. |

The installed JavaScript graph includes libvips (LGPL-3.0-or-later),
lightningcss and axe-core (MPL-2.0), and caniuse-lite (CC-BY-4.0), in addition
to MIT/BSD/ISC/Apache packages. Python includes certifi (MPL-2.0), NumPy and
Matplotlib with bundled notices. These are not all interchangeable with MIT.
Package metadata is an inventory aid, not a substitute for the actual license
and corresponding-source obligations of a distributed binary.

The 23 parameter pairs were reconstructed from the separately licensed sources
above and compared exactly with the local table. This establishes a documented
redistribution basis for the data; it does not settle LUCID's conflicting notices
or prove a historical clean-room process. Retain the separate data licenses.
Do not copy further LUCID source or assert full numerical equivalence; the local
profile is a hybrid with simplified end effects, not the complete Zuber model.

The original notebook, plots and synthetic demonstration belong to this
repository's scientific history. Their existence does not establish
experimental validation. Retain the root author's copyright notice.
