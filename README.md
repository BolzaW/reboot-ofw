# reboot_ofw (`reboot_ofw.bin`)

Micro-payload matériel (`112 octets`) pour **Nintendo Switch** (Erista & Mariko V2 / Lite / OLED avec modchip **Picofly** / **HWFLY** / **RP2040**) permettant d'ajouter un bouton **[100% STOCK OFW]** directement dans le menu **Launch** de **Hekate / Nyx**.

*(English version below)*

---

## 🇫🇷 Présentation

### Le problème
Sur les consoles équipées d'une puce (Mariko `T210B01` avec Picofly/RP2040) et sur les firmwares récents (HOS 21.0.0+ / 23.0.1+) :
* La directive non officielle `ofw=1` présente dans certains anciens packs `hekate_ipl.ini` **n'est pas reconnue** par les versions officielles de `CTCaer/hekate` et provoque un **écran bleu (BSOD)** ou un crash au lancement.
* Le menu `Launch` de Hekate ne propose pas de directive `.ini` native permettant d'appeler la fonction interne du bouton **`Reboot -> OFW`** de Nyx.

### La solution
`reboot_ofw.bin` est un micro-payload écrit en assembleur **ARMv4T** (pour le coprocesseur BPMP ARM7TDMI du Tegra X1) qui reproduit **à l'identique** l'appel matériel `power_set_state(REBOOT_BYPASS_FUSES)` du bouton **`Reboot -> OFW`** de Hekate/Nyx :
1. Nettoie `APBDEV_PMC_SCRATCH0` (`0x7000E450` $\leftarrow$ `0`) pour effacer tout drapeau RCM / recovery / custom.
2. Écrit `PMC_NX_PANIC_BYPASS_FUSES` (`0x21`) dans `APBDEV_PMC_SCRATCH200` (`0x7000EC40`).
3. Déclenche une réinitialisation matérielle immédiate du PMC via le **Watchdog 4 (`TIMER_PMCRESET_EN`)** sur `TMR_BASE` (`0x60005000`), avec repli de sécurité sur `PMC_CNTRL_MAIN_RST`.

**Résultat :**
* La puce (Picofly / HWFLY) reste en veille passive (aucun nouveau glitch n'est déclenché).
* Le SoC redémarre proprement sur sa BootROM interne et lance l'**OFW 100 % Stock** depuis l'eMMC.
* Le `Package1` (`nxbootloader`) officiel contourne la vérification et le brûlage des e-fuses matériels (`BYPASS_FUSES`), ce qui évite tout blocage après une mise à jour effectuée via Daybreak.

---

## 🚀 Installation & Configuration

1. Copiez [`reboot_ofw.bin`](reboot_ofw.bin) sur votre carte microSD dans :
   ```text
   sd:/bootloader/payloads/reboot_ofw.bin
   ```
2. Ajoutez l'entrée suivante dans votre fichier `sd:/bootloader/hekate_ipl.ini` :
   ```ini
   [100% STOCK OFW]
   payload=bootloader/payloads/reboot_ofw.bin
   icon=bootloader/res/ofw.bmp
   ```
   > **Note :** Si vous utilisez `autoboot=...` dans la section `[config]` de votre `hekate_ipl.ini` et que vous ajoutez `[100% STOCK OFW]` en première position, pensez à incrémenter la valeur de `autoboot` de `+1` pour conserver votre entrée de démarrage par défaut.

---

## 🛠️ Compilation (Optionnel)

Le fichier [`reboot_ofw.bin`](reboot_ofw.bin) précompilé est déjà inclus dans ce dépôt. Pour le recompiler et vérifier le désassemblage :

### Avec Python 3 (sans dépendance externe, Windows / Linux / macOS)
```bash
python build.py
```
Le script utilise `arm-none-eabi` s'il est installé, ou assemble directement les instructions ARMv4T puis exécute un désassembleur/vérificateur intégré.

### Avec GNU ARM Embedded Toolchain (`devkitARM` / `arm-none-eabi`)
```bash
make
```

---

## 🇬🇧 English Summary

### Overview
`reboot_ofw.bin` is a tiny (`112-byte`) bare-metal **ARMv4T** payload for the **Nintendo Switch** (Erista & Mariko V2 / Lite / OLED with **Picofly** / **HWFLY** / **RP2040** modchips) that lets you boot **100% Stock OFW** directly from **Hekate's `Launch` menu**.

In official `CTCaer/hekate` releases, the third-party `ofw=1` `.ini` key does not exist and causes a BSOD on Mariko setups when selected from the `Launch` menu. Meanwhile, Nyx's **`Reboot -> OFW`** button works reliably because it triggers a low-level PMC reset via `power_set_state(REBOOT_BYPASS_FUSES)`.

### How It Works
Executed on the Tegra X1 BPMP (`0x40010000`), `reboot_ofw.bin` performs the exact same hardware sequence as Hekate's `Reboot -> OFW`:
1. Clears `APBDEV_PMC_SCRATCH0` (`0x7000E450` $\leftarrow$ `0`).
2. Writes `PMC_NX_PANIC_BYPASS_FUSES` (`0x21`) to `APBDEV_PMC_SCRATCH200` (`0x7000EC40`).
3. Triggers an immediate PMC warm reset via **Watchdog 4 (`TIMER_PMCRESET_EN`)** on `TMR_BASE` (`0x60005000`), with a failsafe fallback to `PMC_CNTRL_MAIN_RST`.

The modchip stays idle on warm reset, the Tegra BootROM boots `Package1` (`nxbootloader`) natively from `BOOT0` in a clean hardware register state, and fuse checks/burning are bypassed (`BYPASS_FUSES`).

### Usage
1. Copy [`reboot_ofw.bin`](reboot_ofw.bin) to `sd:/bootloader/payloads/reboot_ofw.bin`.
2. Add the following section to `sd:/bootloader/hekate_ipl.ini`:
   ```ini
   [100% STOCK OFW]
   payload=bootloader/payloads/reboot_ofw.bin
   icon=bootloader/res/ofw.bmp
   ```
3. To rebuild from source and run the built-in disassembler/verifier:
   ```bash
   python build.py
   ```
