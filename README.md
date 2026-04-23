This python library provides helper methods for eInvoicing and eReporting in France. This lib is used by the Odoo community module l10n\_fr\_einvoicing available on [akretion/fr-einvoicing](https://github.com/akretion/fr-einvoicing), but we would be very happy if other software use it too. The primary goal of this lib is to mutualize code between different versions of the module for different versions of Odoo.

This lib implements the [AFNOR XP Z12-013 standard](https://www.boutique.afnor.org/fr-fr/norme/xp-z12013/-api-pour-interfacer-les-systemes-dinformations-des-entreprises-avec-les-pl/fa300084/466438) for the APIs of the *Accredited Platforms* (*Plateformes Agréées* i.e. PA in French). It will also contain code to generate and parse CDAR XML files to manage the life-cycle of e-invoices.

This lib is currently under development. Consider it as alpha software: method names and arguments can change at any time. Breaking changes will slow down when we reach beta status and it will end when we reach production status.

The AFNOR APIs are fully tested with [SUPER PDP](https://www.superpdp.tech/), but the code should work with any other AFNOR-compliant accredited platform.

## Licence

This library is published under the [GNU Lesser General Public License v2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html) or, at your option, any later version.

## Contributors

* Alexis de Lattre <alexis.delattre@akretion.com>

## Changelog

* version 0.1 dated 2026-04-22

  *  initial release

* version 0.2 dated 2026-04-23

  * Fixes in re-formatting of directory lines for B2G when SIRET has specific global properties
