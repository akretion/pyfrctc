This python library provides helper methods for eInvoicing and eReporting in France. This lib is used by the Odoo community module l10n\_fr\_einvoicing available on [akretion/fr-einvoicing](https://github.com/akretion/fr-einvoicing), but we would be very happy if other software use it too. The primary goal of this lib is to mutualize code between different versions of the module for different versions of Odoo.

This lib implements the [AFNOR XP Z12-013 standard](https://www.boutique.afnor.org/fr-fr/norme/xp-z12013/-api-pour-interfacer-les-systemes-dinformations-des-entreprises-avec-les-pl/fa300084/466438) for the APIs of the *Accredited Platforms* (*Plateformes Agréées* i.e. PA in French). It will also contain code to generate and parse CDAR XML files to manage the life-cycle of e-invoices.

This lib is currently under development. Consider it as alpha software: method names and arguments can change at any time. Breaking changes will slow down when we reach beta status and it will end when we reach production status.

The AFNOR APIs are fully tested with [SUPER PDP](https://www.superpdp.tech/), but the code should work with any other AFNOR-compliant accredited platform.

## Licence

This library is published under the [GNU Lesser General Public License v2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html) or, at your option, any later version.

## Contributors

* Alexis de Lattre <alexis.delattre@akretion.com>

## Changelog

* version 0.9 dated 2026-06-09

  * Add support for MDT-129 in parse\_cdar() and parse\_cdar\_raw()
  * in generate\_cdar(), schemeID attributes are not hard-coded any more. Support for several SchemeIDs for GlobalID nodes

* version 0.8 dated 2026-06-09

  * search\_flows\_parsed() now accepts updated\_after as datetime object (timezone aware or timezone naive as UTC)

* version 0.7 dated 2026-05-28 ([OCA code sprint in Santander](https://www.aeodoo.org/event/spanish-oca-days-2026-143/page/introduccion-spanish-oca-days-2026))

  * Restore method get\_session()
  * Add two new methods authorization\_code\_first\_token() and get\_authorization\_url()
  * Code reformatting for better readability

* version 0.6 dated 2026-05-21

  * Remove method get\_session()
  * Method search\_flows\_parsed() accepts flow\_direction argument with only lowercase letters
  * Methods search\_flow\_parsed(), get\_flow\_metadata\_parsed() and send\_flow\_parsed() returnd an additionnal key **flow_direction** in the flow with value in lowercase letters.

* version 0.5 dated 2026-05-15

  * Add support for MDT-96 in CDAR XML for generation and parsing
  * rename keys doc\_status and doc\_characteristics to their designation in the standard (MDG-37 and MDG-43)

* version 0.4 dated 2026-05-14

  * Add methods to generate and parse CDAR XML files for life cycle

* version 0.3 dated 2026-04-30

  * Add methods send\_flow\_parsed(), search\_flows\_parsed() and get\_flow\_metadata\_parsed()
  * Add multi-page support in search\_flows()

* version 0.2 dated 2026-04-23

  * Fixes in re-formatting of directory lines for B2G when SIRET has specific global properties

* version 0.1 dated 2026-04-22

  *  initial release
