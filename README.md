Circular Factory Ontologies (circularfactory.github.io)
===

A suite of ontologies for the circular factory:
* Core (https://w3id.org/circularfactory/Core) - The central ontology of the circular factory

Contributing projects:
* SFB1574 (https://www.sfb1574.kit.edu/) - The circular factory for the pepetual innovative product.

Contributing organizations:
* Karlsruhe Institute of Technology (KIT)
* University of Stuttgart
* Aalen University

Homepage:
* https://w3id.org/circularfactory

Contacts: 
* Ratan Bahadur Thapa  <ratan.thapa@ki.uni-stuttgart.de>
* Daniel Hernández <daniel.hernandez@ki.uni-stuttgart.de>
* Etienne Hoffmann <etienne.hoffmann@kit.edu>
* Jan-Felix Klein <jan-felix.klein@kit.edu>

The front page
---

`index.html` at the root is generated. Do not edit it by hand: the `Front door` workflow
overwrites it on a daily schedule, and on demand from the Actions tab.

A repository in this organization is listed on it when that repository carries the topic
`cf-tool` or `cf-ontology`. The same topic sorts it into its section. Registration is opt-in,
so a repository nobody has tagged is never advertised.

What an entry says comes from that repository's own `description` and `homepage`. A repository
with no description renders as its name and its link, and nothing here writes copy on its
behalf. To add or change an entry, edit those fields on the repository itself; the change
appears on the next run.

The generator is `.github/scripts/build_front_door.py`. It reads only public repository
metadata, needs no credential, and prints no version numbers - each entry links `latest/`, so
a release changes nothing on this page. Run `python3 .github/scripts/build_front_door.py --help`
for its options.