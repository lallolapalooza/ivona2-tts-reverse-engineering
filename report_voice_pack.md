# IVONA 2 voice pack — APK contract specification

Target: how a voice pack APK (e.g. `com.ivona.tts.voicebeta.eng.usa.kendra` v1.6.23.422) is built, what it must ship on disk, and how the IVONA engine app (`com.ivona.tts` v1.6.55.617) discovers/uses it — precise enough to reimplement a voice pack from scratch.

Evidence paths (all relative to `/home/asdf/Downloads/ivona_re/`):

* `out/jadx_kendra/{sources,resources}` — decompiled Kendra pack (original APK: `IVONA 2/IVONA Kendra US English beta_v1.6.23.422_apkfab.com/com.ivona.tts.voicebeta.eng.usa.kendra.apk`)
* `out/jadx_amy/{sources,resources}` — decompiled Amy pack (original: `IVONA 2/com.ivona.tts.voicebeta.eng.gbr.amy_1623422_apkplz.net/…apk`)
* `out/jadx_tts/sources`, `out/jadx_tts_res/resources`, `out/tts/` — decompiled engine app (original: `IVONA 2/IVONA Text-to-Speech HQ 1.6.55.617.apk`)
* `out/ghidra_dump/libtiver.c` — Ghidra decompilation of `libtiver.so` (ARM; dump addresses = ELF address + 0x10000)
* `out/libs/{kendra,amy}/*.so`, `out/tts/lib/armeabi/libttsivona.so`
* Store listings: `IVONA 2/*/manifest.json` (XAPK metadata produced by the mirror store, not by the APK itself)

Unverified items are marked **[INFERENCE]**.

---

## 1. Manifest contract

Source: `out/jadx_kendra/resources/AndroidManifest.xml` (Amy's differs **only** in package/class names — verified by `diff`).

### 1.1 Manifest header

```xml
<manifest android:sharedUserId="com.ivona.ttsuser"
          android:versionCode="422"
          android:versionName="1.6.23.422"
          package="com.ivona.tts.voicebeta.eng.usa.kendra">
  <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"/>
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
  <uses-permission android:name="android.permission.ACCESS_WIFI_STATE"/>
  <uses-permission android:name="android.permission.READ_PHONE_STATE"/>
  <uses-permission android:name="com.android.vending.CHECK_LICENSE"/>
  <uses-permission android:name="android.permission.WAKE_LOCK"/>
  <uses-sdk android:minSdkVersion="4"/>
```

* **`sharedUserId="com.ivona.ttsuser"`** — the engine declares the same `sharedUserId` (`out/jadx_tts_res/resources/AndroidManifest.xml:2`). This is the primary discovery mechanism: the engine enumerates its own UID's packages with `getPackagesForUid(Process.myUid())` (`out/jadx_tts/sources/com/ivona/ttslib/packages/IvonaPackagesInfo.java:110`).
* **Shared UID requires a shared signing key.** Verified: engine, Kendra and Amy APKs are all signed by the identical certificate — `CN=IVONA Software Sp. z o.o., OU=IVONA, O=IVONA Software Sp. z o.o., L=Gdynia, ST=Pomorskie, C=PL`, serial `4dc5e80d`, SHA1 `64:7A:B1:77:5F:DF:0C:8E:EA:BA:A3:98:4A:77:91:EA:B9:35:E4:97` (`keytool -printcert` on `META-INF/CERT.RSA` of each APK). A reimplemented pack must be signed with the same key as the engine (or both must be re-signed together), otherwise installation fails with a UID/signature mismatch.
* `minSdkVersion=4`; no `targetSdkVersion`.
* `versionCode`/`versionName` are duplicated into store metadata (`manifest.json` `"version_code":"422"`, `"version_name":"1.6.23.422"`).

### 1.2 Components (exact declarations)

| Element | android:name | Filter / notes |
|---|---|---|
| `<application>` | `com.ivona.tts.voicebeta.eng.usa.kendra.VoiceApp` | `label=@string/app_name`, `icon=@drawable/icon` |
| `<activity>` | `com.ivona.tts.voicebeta.eng.usa.kendra.IvonaVoice` | theme `@android:style/Theme.NoTitleBar`, `screenOrientation=portrait`, filter `android.intent.action.MAIN` + `android.intent.category.LAUNCHER` |
| `<activity>` | `CheckVoiceInstalled` (relative ⇒ `<pkg>.CheckVoiceInstalled`) | theme `@android:style/Theme.NoDisplay`, filter action **`com.ivona.tts.CHECK_VOICE_INSTALLED`** + `android.intent.category.DEFAULT` |
| `<service>` | `.DownloadVoiceFilesService` | **dead entry**: no class of this name exists anywhere in `classes.dex` (`grep -c DownloadVoiceFiles …/classes.dex` → 0) |
| `<receiver>` (element 1) | `com.ivona.tts.voicelib.ActivityReceiver` | `android.intent.action.USER_PRESENT` |
| `<receiver>` (element 2) | `com.ivona.tts.voicelib.ActivityReceiver` (same class, second element) | `PACKAGE_ADDED`, `PACKAGE_CHANGED`, `PACKAGE_REMOVED`, `PACKAGE_RESTARTED`, `PACKAGE_FULLY_REMOVED`, `PACKAGE_REPLACED` + `<data android:scheme="package"/>` |
| `<receiver>` | `<pkg>.UpdateReceiver` | `android.intent.action.PACKAGE_REPLACED` + `<data android:scheme="package"/>` |
| `<service>` | `com.ivona.tts.voicelib.VoiceDownloaderService` | Google Play expansion downloader (§4) |

There are **no `<meta-data>` entries** anywhere in the pack manifest (the only `meta-data` in the project is the engine's `android.speech.tts` → `@xml/tts_engine`). No permissions beyond the eight above; no `RECEIVE_BOOT_COMPLETED` (the engine has that, the pack does not).

### 1.3 `android.intent.category.tts_lang.*` — where those really live

The voice-pack manifest contains **no** `tts_lang` categories (grep over both packs' manifests/sources → 0 hits). Those categories belong to the **engine** app, on `com.ivona.tts.Ivona` (`out/jadx_tts_res/resources/AndroidManifest.xml:60-80`): action `android.intent.action.START_TTS_ENGINE` with categories `android.intent.category.tts_engine.IVONA`, `tts_lang.eng`, `tts_lang.eng.USA`, `tts_lang.eng.GBR`, `tts_lang.pol`, `tts_lang.deu`, `tts_lang.fra`, `tts_lang.spa`, `tts_lang.spa.ESP`, `tts_lang.spa.USA`, `tts_lang.ron`. A pack does not advertise languages via intent categories; language identity comes from the package name (§3.1).

### 1.4 What the engine relies on when discovering a pack

1. Same `sharedUserId` + same signer → pack appears in `getPackagesForUid()` (see §1.1).
2. Package-name shape `com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>` — the engine parses it natively (adjacent strings `com.ivona.tts.` / `.voicebeta.` in `out/tts/lib/armeabi/libttsivona.so`) and in Java: `IvonaPackage.a(String)` splits the package name and requires ≥7 dot-separated parts, `new Locale(split[4], split[5], split[6])` (`out/jadx_tts/.../packages/a.java:15-24`).
3. Presence of these files inside the pack (strings in engine `libttsivona.so`): `/lib/libtiver.so`, `/lib/libttsivonavoice.so`, `Android/obb/`, `ivona/`, `/data/data/` — i.e. the engine reaches into the pack's native-lib directory and OBB directory **[INFERENCE: exact access mechanism (dlopen vs file read) not verified; engine-side native code not disassembled for this report]**.
4. A component named `<pkg>/.IvonaVoice` with MAIN/LAUNCHER — the engine re-launches it *by literal name* when a voice is not fully installed: `ComponentName.unflattenFromString(this.h + "/.IvonaVoice")` (`out/jadx_tts/.../IvonaGui.java:145-146`). A pack that renames its launcher activity breaks this path.
5. A display-name registry: static map `com.ivona.ttslib.packages.c` lists every known package → `"IVONA Kendra"`, `"IVONA Amy"` … (`out/jadx_tts/.../packages/c.java`), merged with the runtime cache `ivona_pkgs.csv` (§6.3).
6. The pack's own service/activity endpoints it pokes (§4.4): `com.ivona.ttslib.CustomSettingsService` (extra `upkgmon`), `com.ivona.ttslib.engine.TTSServiceActivation`, activity `com.ivona.ttslib.CheckVoiceData`, activity `com.ivona.ttslib.IvonaGui`.
7. **Not** used by the shipped engine: the `com.ivona.tts.CHECK_VOICE_INSTALLED` filter. `grep -ao "checkVoice\|CHECK_VOICE_INSTALLED" out/tts/classes.dex` → 0 hits. The protocol still exists in the pack (§3.3) and must be implemented for compatibility with older engines, but engine 1.6.55.617 never calls it.

---

## 2. What a voice pack ships on disk

### 2.1 Files inside the APK (16 entries total, Kendra)

```
res/layout/main.xml
res/layout/status_bar_ongoing_event_progress_bar.xml
AndroidManifest.xml
resources.arsc
res/drawable-{h,l,m}dpi/icon.png
res/drawable-{h,m}dpi/notify_panel_notification_icon_bg.png
classes.dex                       (117 992 B)
lib/armeabi/libvoice_en_us_kendra.so   (3 085 840 B)   ← voice-specific data/code
lib/armeabi/libtiver.so                (124 164 B)     ← install verifier + voice table
lib/armeabi/libttsivonavoice.so        (1 637 476 B)   ← TTS core (identical in every pack)
META-INF/MANIFEST.MF, CERT.SF, CERT.RSA
```

No `assets/` directory, no `res/xml`, no config files in the APK. `libtiver.so` and `libttsivonavoice.so` are **byte-identical** between Kendra and Amy (md5 `b381ee3b994d615c997f1b0ddd1b09bd`, `2274b82e216f8dd4123deea94e00511c`); only `libvoice_*.so` differs.

### 2.2 OBB naming and directory layout

Actual files in the distributions (`IVONA 2/…/Android/obb/<pkg>/`):

```
main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb     152 219 597 B
patch.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb         74 861 B   (zip)
main.199.com.ivona.tts.voicebeta.eng.gbr.amy.obb       149 905 560 B
patch.199.com.ivona.tts.voicebeta.eng.gbr.amy.obb           74 861 B   (zip)
```

* Path root constant: `com.google.android.vending.expansion.downloader.a` (`Constants.java`): `File.separator + "Android" + File.separator + "obb" + File.separator` → `/Android/obb/` (`out/jadx_kendra/sources/com/google/android/vending/expansion/downloader/a.java`).
* File names: `main.<N>.<package>.obb` / `patch.<N>.<package>.obb`. **`<N>` is the expansion version, not necessarily the APK `versionCode`** (422 here, but 199/183/422 appear per voice). Where `<N>` comes from:
  * main: from a table entry inside the pack's own `libtiver.so` (§2.4) — for Kendra/Amy it is `199`.
  * patch: **hardcoded string `"patch.199."`** in `libtiver.so` (rodata vaddr 0x18b86) — the patch file is *always* `patch.199.<pkg>.obb` regardless of `versionCode`.
  * downloader: from the Play licensing response (`FILE_NAME<n>` extras, §4.2) — no name is hardcoded in Java (grep for `main.`/`Android/obb` in dex sources → no hits).
* Store mirror metadata (`IVONA 2/*/manifest.json`) records the same paths, `"install_location":"EXTERNAL_STORAGE"` and `"total_size":154764760` (Kendra) / `152446951` (Amy) — that JSON is produced by the mirror's XAPK tooling (`"xapk_version":1`), not shipped by the APK.

Expected runtime layout:

```
/sdcard/Android/obb/<pkg>/main.<N>.<pkg>.obb
/sdcard/Android/obb/<pkg>/patch.199.<pkg>.obb
/sdcard/Android/obb/<pkg>/lang_en_us.dat      ← extracted from the patch zip by libtiver (§2.4)
```

### 2.3 Java-side install path resolution — `VoiceFiles` (`out/jadx_kendra/sources/com/ivona/tts/voicelib/VoiceFiles.java`)

```java
static { System.loadLibrary("tiver"); }
private static native int checkFiles(String str, String str2);

public static boolean a(Context context) {
    String name = context.getApplicationContext().getClass().getName();   // "<pkg>.VoiceApp"
    String substring = name.substring(0, name.lastIndexOf("."));          // "<pkg>"
    // walk back exactly 3 dots:
    ... length = substring.lastIndexOf(46, length - 1);  // 3 iterations
    String substring2 = substring.substring(length + 1); // "eng.usa.kendra"
    q a = q.a(substring2);                                // legacy-file table
    String absolutePath = Environment.getExternalStorageDirectory().getAbsolutePath();
    // delete legacy pre-OBB files:
    //   /sdcard/ivona/<vox_file>   e.g. vox_en_us_kendra22v
    //   /sdcard/ivona/<lang_file>  e.g. lang_en_us.dat
    int checkFiles = checkFiles(substring, absolutePath + "/");
    return checkFiles == 0;
}
```

* Voice identity for the check is derived from the **Application class name** → `<pkg>` → `"eng.usa.kendra"`.
* Legacy cleanup table `q` (`voicelib/q.java`), key → old files (14 rows), e.g. `eng.usa.kendra → vox_en_us_kendra22v / lang_en_us.dat`, `eng.gbr.amy → vox_en_gb_amy22v / lang_en_gb.dat`, plus `cym.gbr.gwyneth, deu.deu.marlene, eng.aus.nicole, eng.gbr.gwyneth, spa.esp.conchita, spa.usa.penelope, fra.fra.celine, isl.isl.dora, ita.ita.giorgio, pol.pol.maja, por.bra.vitoria, ron.rou.carmen`. A key miss returns `null` and simply skips cleanup.
* Success is defined solely as **`checkFiles(...) == 0`**.

### 2.4 Native validation — `libtiver.so` `Java_com_ivona_tts_voicelib_VoiceFiles_checkFiles`

(Ghidra dump `out/ghidra_dump/libtiver.c`; ELF base address 0x6a64; corroborated by `strings`/ELF decoding of `out/libs/kendra/libtiver.so`.)

1. `checkFiles(pkgPath, "<sdcard>/")` (dump 0x16a64): builds `"<sdcard>" + "Android/obb/"`, then calls the checker with `(pkgPath, "<sdcard>/Android/obb/", 1)`. JNI-string failures log `Failed to obtain package name.` / `Failed to obtain path to files.` under tag **`IVONAVOICE`** and return `-2`.
2. `FUN_000169b8(pkg, obbDir, flag)` (0x69b8): linearly scans a 48-byte-stride table at `.data.rel.ro.local` (vaddr 0x1d538) matching field[4] = package name; builds `obbDir + "/" + pkg + "/" + table[8]` (table[8] = main-obb file name, e.g. `main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb`) and `stat()`s it.
   * stat fails → **return 1** (not installed);
   * size mismatch → **return 1**;
   * size matches → run the patch step (below) and return its result (0 = OK).
   The size operand is compared against table field[9], which is the **exact expected main-obb byte size** — verified: Kendra table value `152219597` = actual `main.199….kendra.obb` size (unique occurrence in the .so at file offset 116828); Amy `149905560` likewise. A second stat operand is printed as `== 0`; taken together the condition is semantically *"64-bit file size equals expected size"* (Ghidra's `st_blksize`/`st_blocks` labels are offset-shifted w.r.t. the real ARM `struct stat`; the `== 0` half is best read as the high half of a <4 GiB size) — **[INFERENCE]** on the exact field mapping; the size-equality requirement itself is verified.
3. `FUN_000166e8(entry, obbDir, flag)` (0x66e8): opens `obbDir + "/" + pkg + "/patch.199." + pkg + ".obb"` with minizip (`unzOpen`; failure log `Error on opening patch file:%s`, return -1), iterates entries (`unzGetGlobalInfo`, `unzGetCurrentFileInfo`, `unzGoToNextFile` until -100), skips names containing `/` or `\`, and extracts each entry to `obbDir + "/" + pkg + "/" + entryName` through an 8 KiB buffer (`unzOpenCurrentFile` → `fopen("wb")` → `unzReadCurrentFile` → `fwrite`), re-extracting when `flag==0`, the target is missing, or its size does not match the zip entry. Error strings: `Error %d on reading patch data`, `Error %d on getting file info`, `Error opening current file!`, `Error creating file:%s`, `Error reading patch file:%s`, `Error on writting file:%s.`, `Error %d on switching to next file`. Returns 0 on success, -1 on failure.

So the *only* integrity checks are: **main OBB existence + exact byte size** (against a constant compiled into `libtiver.so`) and **zip readability of the patch** (whose entries are re-extracted as needed). There is **no checksum** (no MD5/SHA anywhere in pack code or `libtiver.so`; the bundled Google downloader helpers `…/downloader/l.java` compare `file.length() == size` only).

### 2.5 Downloader-side bookkeeping (`com.google.android.vending.expansion.downloader`)

* Save path: `l.a(Context)` = `Environment.getExternalStorageDirectory() + "/Android/obb/" + packageName`; `l.a(Context, fileName)` adds `"/" + fileName`.
* Existence/size check `l.a(Context, name, size, deleteOnMismatch)`: `file.exists() && file.length() == size` else (optionally) `delete()` (`…/downloader/l.java:74-85`).
* SQLite `DownloadsDB` (version 7): table `DownloadColumns` = `FN, URI, ETAG, TOTALBYTES, CURRENTBYTES, LASTMOD, STATUS, CONTROL, FAILCOUNT, RETRYAFTER, REDIRECTCOUNT, FILEIDX`; table `MetadataColumns` = **`APKVERSION`, `DOWNLOADSTATUS`, `DOWNLOADFLAGS`** (`…/downloader/impl/v.java`, `…/impl/x.java`, `…/impl/w.java`).
* Version bookkeeping: `DownloaderService.a(u, PackageInfo)` returns "stale" when `stored APKVERSION != packageInfo.versionCode` (0 stashes/forces the LVL re-check path; `…/impl/DownloaderService.java:165-166`), and the LVL callback stores the current `versionCode` into the DB (`…/impl/t.java:71`).
* Engine-side bookkeeping: `IvonaPackagesInfo.c()` rebuilds `ivona_pkgs.csv` whenever any shared-UID package is missing from the cache **or its `versionCode` differs** (`…/packages/IvonaPackagesInfo.java:66-104`).

### 2.6 OBB content formats

**main OBB** — not a zip; proprietary container:

```
00000000: 4344 5856 766f 785f 656e 5f75 735f 6b65  CDXVvox_en_us_ke
00000010: 6e64 7261 0000 ... (name padded to 0x20)
00000020: 0000 0000 2256 0000 0e00 0000 187a 7c4f  ...."V.......z|O
```

* magic `CDXV` + ASCII voice-data name `vox_en_us_kendra` (Amy: `vox_en_gb_amy`) — matches the legacy file names in `q` minus the `22v` suffix;
* `0x5622 = 22050` at 0x24 (sample rate **[INFERENCE]**), `0x0e` at 0x28, a 32-bit word `0x4f7c7a18` (crc or 2013-era timestamp **[INFERENCE]**), `0x68` at 0x30 (TOC/header size), followed by offset/length pairs. `libvoice_en_us_kendra.so` also contains `CDXV` and `vox_en_us_kendra` strings (it reads this format); no XML, no `IVONAVOICE` marker inside the OBB (`IVONAVOICE` is only the log tag in `libtiver.so`).

**patch OBB** — a standard zip (minizip-readable), single entry:

```
lang_en_us.dat   74 668 B  (Kendra)      lang_en_gb.dat  74 668 B (Amy)
```

whose payload starts `ISEF 00 00 00 01` (proprietary "IVONA …" blob **[INFERENCE on ISEF meaning]**). This file is what `checkFiles` extracts next to the OBBs; the pack's `libttsivonavoice.so` consumes it (it contains strings `lang_`, **`IVONA_LANG_DAT_DIR`**, `IVONA_Lexicon: Missing file header`, `vox_lexicon`).

`english.lex` (table field[10]) does **not** appear in either OBB or the APK; lexicon paths are engine-configured (`lex_dir`, §6.2) **[INFERENCE]**.

---

## 3. Voice metadata

### 3.1 Locale identity — encoded in the package name

`com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>` where the segments are **3-letter ISO 639-2 language**, **3-letter ISO 3166-2-letter-extended country** (Java's `Locale` ISO3 forms), and voice name as *variant*:

```java
// out/jadx_tts/.../packages/a.java
public static Locale a(String str) {           // split.length must be >= 7
    String[] split = str.split("\\.");
    return new Locale(split[4], split[5], split[6]);   // "eng", "USA", "kendra"
}
public String h() { return e.getISO3Language() + "-" + e.getISO3Country(); }  // "eng-USA"
public Locale f() { return new Locale(e.getISO3Language(), e.getISO3Country()); }
```

Kendra: `eng`/`USA`/`kendra` ⇒ `"eng-USA"`; Amy: `eng`/`GBR`/`amy` ⇒ `"eng-GBR"`. `IvonaPackagesInfo.a(lang, country, variant, …)` scores candidates by exact ISO3 match (language < country < variant). The pack's own native table duplicates the same codes (field[0]/field[1] of `libtiver.so`, §A).

### 3.2 Per-voice strings (`out/*/resources/res/values/strings.xml`)

| resource | Kendra | Amy |
|---|---|---|
| `app_name` / `textViewVoiceName` | `IVONA Kendra US English beta` | `IVONA Amy UK English beta` |
| `textViewVoiceInfo` | `US English female voice` | `UK English female voice` |
| `voice_welcome_text` | `Hello there, my name is Kendra. …` | `Hi, My name is Amy, …` |
| `TAG` (log tag) | `IvonaKendra` | `IvonaAmy` |
| `libvoice` | `com.ivona.tts.voicebeta.eng.usa.kendra/lib/libvoice_en_us_kendra.so` | `com.ivona.tts.voicebeta.eng.gbr.amy/lib/libvoice_en_gb_amy.so` |
| `app_icon` | `en_us` | `en_gb` |

* `libvoice` = `<pkg>/lib/<libvoice_name>` — the pack's voice-identity handle: `VoiceApp.a()` (= `AppLib`/`ResourceReader.b.a()`) returns it, and `CheckVoiceInstalled` compares requests against it (§3.3).
* `app_icon` is passed to the engine, which maps it to its own drawable: `en_us, en_gb, pl, de, es, es_us, fr, ro, cy, en_wls, en_au, it, is` → `icon_<x>.png` (`IvonaGui.a(String)`; unknown values are ignored). Engine ships `icon_en_us.png`, `icon_en_gb.png`, etc.
* `values-pl/strings.xml` carries Polish `app_name`, `textViewVoiceName`, `textViewVoiceInfo` (`IVONA Kendra Angielski US beta`, `IVONA Amy Angielski GB beta` — see also `manifest.json` `"locales_name":{"pl":…}`). `libvoice`/`TAG`/`app_icon`/`voice_welcome_text` exist only in the default locale.
* `res_lang` = `en` (both); `current_eula_version` = `10` (integer, both).
* Other contract-relevant strings: `eula` (full HTML EULA, "IVONA End User License Agreement / Version 1.0"), `textViewRecommendWiFi` and `text_paused_cellular` containing the literal placeholder `%file_size%` (replaced by `IvonaVoice.b(int)` with `f()`), `state_*` download-state strings, `notify_*` errors, `continue_update`, `textViewInstallIvonaTts`, `textViewUpdateIvonaTts`, `market_not_available`, `notify_init_error`.
* Display-name strings are **also** in the pack's `libtiver.so` table (`IVONA Kendra` / `IVONA Amy`, field[3]) — shorter form than `app_name`.

### 3.3 `CheckVoiceInstalled` — request/response protocol (legacy but part of the contract)

Manifest: activity `<pkg>.CheckVoiceInstalled`, theme `Theme.NoDisplay`, action `com.ivona.tts.CHECK_VOICE_INSTALLED`, category `DEFAULT`. Base class `com.ivona.tts.voicelib.CheckVoiceInstalled`; subclass only supplies the log tag (`"eng.usa.kendra.CheckVoiceInstalled"` / `"eng.gbr.amy.CheckVoiceInstalled"`).

**Intent extras:** request extra **`checkVoice`** (`byte[]`); result extra **`checkVoiceResult`** (`byte[]`); always `setResult(0, intent)` + `finish()`.

**Wire format** (`com.ivona.tts.commonlib.a.*`, `compiled from: Request.java / Response.java / CryptedReader / CryptedWriter / Utils`):

* Framing: `int32` big-endian length + that many raw bytes (strings are length-prefixed, no NUL).
* Cipher: byte-wise **XOR** with the fixed 64-byte key of `Request.a`:
  `D1 29 84 E7 F8 7B C9 91 C3 3A B0 CE 09 30 F3 5A F3 30 11 2A 68 64 14 D2 0E 27 2B 30 73 B0 01 10 15 C4 B5 BA A1 DD D8 C5 F6 BB 87 2E 22 CB 17 B7 98 55 BB 49 E5 5C 6D 56 E4 95 C6 35 DC 27 E0 7E` (source literal: `{-47, 41, -124, -25, -8, 123, -57, -111, -61, 58, -80, -50, 9, 48, -13, 90, -13, 48, 17, 42, 104, 100, 20, -46, 14, 39, 43, 48, 115, -80, 1, 16, 21, -60, -75, -70, -95, -35, -40, -59, -10, -69, -121, 46, 34, -53, 23, -73, -104, 85, -69, 73, -27, 92, 109, 86, -28, -107, -58, 53, -36, 39, -32, 126}`).
* **Request plaintext** = `[len]"Check voice installed" [len]<voiceId> [len]<payload>`; parsed as `new Request(RequestCode.a(str), str2, bytes)`. `RequestCode` enum: `CHECK_VOICE_INSTALLED(1, "Check voice installed")` — the lookup compares the description string (`d.a(String)` in jadx output always returns `values()[0]`; with a single enum value any of name/description works, but the description is what the source compares **[INFERENCE on exact original loop]**).
* Pack checks: `request.voiceId.equals(((AppLib)getApplicationContext()).a())` (i.e. equals the pack's `R.string.libvoice`) **AND** `request.code == CHECK_VOICE_INSTALLED` (the file check `b()` unconditionally returns `true` → once an APK is installed and the OBBs are present it answers installed; note this path does **not** call `VoiceFiles.a()`).
* **Response plaintext** = `[len]"Voice is installed"` or `[len]"Voice is not installed"`, then `[len]<voiceId>` — XOR-encrypted with **the request's `payload` bytes as key** (`Response.a()` → `new CryptedWriter(payload); w.a(code.toString()); w.a(voiceId); w.a()`). Enum: `VOICE_INSTALLED(1, "Voice is installed")`, `VOICE_NOT_INSTALLED(1, "Voice is not installed")` (both have integer value 1; only the description travels on the wire).

### 3.4 Pack → engine handoff extras (the live protocol)

From `com.ivona.tts.voicelib.IvonaVoice.j()` — after verifying `com.ivona.ttslib.CheckVoiceData` resolves (query only; the extra it sets, `IvonaLibvoices`, is never delivered — no `IvonaLibvoices` string exists in the engine dex) and engine `versionCode >= 183`, the pack starts:

```java
Intent("android.intent.action.VIEW") component com.ivona.tts/com.ivona.ttslib.IvonaGui
  extra "VoicePackage"       = getPackageName()            // must match engine's registry key
  extra "welcome_text"       = getString(R.string.voice_welcome_text)
  extra "app_name"           = getString(R.string.app_name)
  extra "voice_info"         = getString(R.string.textViewVoiceInfo)
  extra "app_icon"           = getString(R.string.app_icon)   // "en_us"/"en_gb"
  extra "dont_return_to_gui" = true
```

All five are consumed by `IvonaGui.onCreate` (`out/jadx_tts/.../IvonaGui.java:92-127`). If the voice state is not `FULL_INSTALLED`, the engine relaunches `<pkg>/.IvonaVoice` **only when `pack.versionCode == engine.versionCode`**, otherwise shows an update dialog (`IvonaGui.java:145-165`); it forwards `dont_return_to_gui` back into the pack intent (`IvonaGui.java:151`), and the pack then toasts `notify_init_error` and finishes.

Install-state enum consumed by the engine (`packages/b.java`): `FULL_INSTALLED(0)`, `APK_INSTALLED(1)`, `FILES_WITHOUT_APK(2)`, `UNKNOWN(-1)` — i.e. the engine distinguishes "APK present", "only OBB data present", "both".

---

## 4. Download flow

### 4.1 UI/entry flow (`com.ivona.tts.voicelib.IvonaVoice`, 381 lines)

1. `setContentView(R.layout.main)`; SharedPreferences file **`ivona_package`**, key **`agr_int_ver`**; if `agr_int_ver < R.integer.current_eula_version (10)` → show `WebView` with `R.string.eula` in dialog 10: positive `"OK"` stores the version and proceeds, negative (`R.string.cancel`) finishes.
2. `b(true)`: `VoiceFiles.a(this)` → if files invalid, call Google's `DownloaderService.a(ctx, PendingIntent.getActivity(re-launch own activity, flags 335544320), VoiceDownloaderService.class)`; nonzero return → reveal download panel (`llDownloadCtrls`); zero (all files present) → `ActivityReceiver.a(ctx)` (poke engine, §4.4) + `j()` (engine checks / handoff, §3.4).
3. Download callbacks implement `com.google.android.vending.expansion.downloader.m`: `a(int state)` (state 5 = completed ⇒ `b(false)` ⇒ handoff), `a(DownloadProgressInfo)` (progress bar, `%` from `current*100/total`, `l.a(done,total)` → `"x.xxMB / y.yyMB"`), `a(Messenger)` binds the client.
4. `f()` (per-voice override) returns **250** in *both* packs — the `%file_size%` UI hint ("approx. %file_size%MB"), not a real size (real OBB total ≈ 152.3 MB).
5. If the engine is missing: `textViewInstallIvonaTts` + button opens `market://details?id=com.ivona.tts`; if engine `versionCode < 183`: `textViewUpdateIvonaTts` + button. On API < 8 it additionally requires the old `com.google.tts` TTS (`com.google.tts.TextToSpeechSettings`, install link `http://eyes-free.googlecode.com/files/tts_3.1_market.apk`). FAQ link built as `http://mobile.faq.ivona.com/pkb_mobile_i4m?l=<pl|en_US>#home/l:…` from the device ISO3 language.

### 4.2 `VoiceDownloaderService` + Google Play expansion downloader

`com.ivona.tts.voicelib.VoiceDownloaderService extends com.google.android.vending.expansion.downloader.impl.DownloaderService` and implements the three abstract hooks:

| override | meaning | value |
|---|---|---|
| `j()` | alarm receiver class (used in `DownloaderService.b(long)` → `AlarmManager` intent `android.intent.action.DOWNLOAD_WAKEUP`, `setClassName(getPackageName(), j())`, extra `EPI`) | `com.ivona.tts.voicelib.VoiceDwnldAlarmReceiver` |
| `h()` | Play licensing **RSA public key** | `MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAipWjiqMwmVmWPrGXTAOY5m3aTNScWGtigFhfnIjIP0JBoMbuXnsVN+L/4sifcq3hSNTVTQimIWqodl0ZvFlmBjpcLq1dbVpVzZRy3VhpDVe38xGCXQGI6C9WR/UsuRXPReKC/dRfeyl9a+qPpvjrAWeQBesmEUwG6D0RqklkjiCp9+0gcEwlO+Q2VG+B51ktzxaU5cV0t2AZJz9MLp+gRJ2eNRjt17cg05yOppM9+LxSJ/l+TqzLOyX9HtSFnAS7eYf8Sm+a8EUmCMh47VbE8+/CIscmMMIT1qet87+Jfh232w2deRFrwa5cYEgsMb54/eO31ky0ZZAiW97uNstttwIDAQAB` |
| `i()` | AES **salt** (30 bytes) for `AESObfuscator` | `{-103, 116, 89, -42, -114, 69, 74, -65, -101, 19, 103, -63, -118, -49, -120, -2, -108, -79, -37, -127, 111, -90, -24, 10, 2, -50, -62, 66, -110, 18}` = `99 74 59 D6 8E 45 4A BF 95 13 67 C1 8A CF 88 FE 94 B1 DB 81 6F A6 E8 0A 02 CE BE 42 92 12` |

Flow (classes under `com.google.android.vending.*` bundled in the pack dex):

1. Service start requires a caller-supplied `PendingIntent` extra **`EPI`**; otherwise it logs `Downloader started in bad state without notification intent.` and returns.
2. Runnable `impl/s`: `new com.google.android.vending.a.b(ctx, new a.a(publicKey, packageName, Settings.Secure.ANDROID_ID))` → binds the Play licensing service (`ILicensingService`; the base64 blob `Y29tLmFuZHJvaWQudmVuZGluZy5saWNlbnNpbmcuSUxpY2Vuc2luZ1NlcnZpY2U=` decodes to `com.android.vending.licensing.ILicensingService`) → `com.google.android.vending.a.j(...)` license request.
3. `com.google.android.vending.a.b` (`compiled from: APKExpansionPolicy`) parses the LVL response extras **`FILE_URL<n>` / `FILE_NAME<n>` / `FILE_SIZE<n>`** (plus `GR`, `GT`, `VT` grace/validity fields) — **the OBB file names, sizes and download URLs come from Google Play, not from the APK**. Strings in the same package: `AES/CBC/PKCS5Padding`, `com.android.vending.licensing.AESObfuscator-1|`, `com.android.vending.licensing.APKExpansionPolicy`, `LicenseValidator`, `SHA1withRSA`.
4. Callback `impl/t.a(int)` (`n.a` of the policy): for each file — if `l.a(ctx, name, size, true)` passes (exists with exact length) it is marked `STATE_SUCCESSFUL (h=200)`; else flagged for download; then `u.a(ctx)` stores `APKVERSION = versionCode` and recursion-guards via `DownloaderService.a(ctx, pendingIntent, cls)`.
5. Download executes over Apache HttpClient (`impl/k.java`), with Range resume/proxy handling; response `Content-Type` must be **`application/vnd.android.obb`** (checked at `impl/k.java:457`), `attachment; filename="…"` accepted as a name source (`…/downloader/l.java` pattern). Failures map to the pack's `state_failed_*` strings (incl. `state_failed_unlicensed` = "Download failed because you have not downloaded this app from Google Play").
6. Progress/state are pushed to the UI via messenger (`DownloadProgressInfo{total,current}`) and a custom notification (`res/layout/status_bar_ongoing_event_progress_bar.xml`, strings `time_remaining_notification`, `kilobytes_per_second`, `state_paused_*`).
7. Wakeups: `AlarmManager` → `android.intent.action.DOWNLOAD_WAKEUP` → **`VoiceDwnldAlarmReceiver`** → `com.google.android.vending.expansion.downloader.c.a(context, intent, VoiceDownloaderService.class)` (restart the service with the original `EPI`).

**Endpoints:** no download/licensing URL is hardcoded in the pack (full-text grep for `http` in both packs yields only the FAQ URL and the eyes-free TTS link). Traffic goes to whatever host Play's licensing/delivery response provides **[INFERENCE: host not observable offline]**.

### 4.3 Notification resources

Downloader notification text uses the pack's `notification_download_complete` / `notification_download_failed`, `notify_dwnld_ok`, etc.; icon `R.drawable.icon`; string `downloadInProgress` ("Voice data is downloading. …").

### 4.4 First launch / update receivers

**`<pkg>.UpdateReceiver` → `voicelib/UpdateReceiverLib.onReceive`** (action `PACKAGE_REPLACED`):

1. If extras contain `android.intent.extra.UID`, resolve `getPackagesForUid(uid)[0]` and ignore the broadcast unless it equals the pack's own package (shared UID caveat: `getPackagesForUid` may return several packages; the code takes `[0]` **[observation]**).
2. `VoiceFiles.a(context)` → if files are *not* OK, post **notification id 2**: icon `R.drawable.icon`, ticker/content text `R.string.continue_update` ("Click to complete the install process."), content title `R.string.app_name`, `flags |= 16 (FLAG_AUTO_CANCEL)`, content intent = start `<pkg>.IvonaVoice` with intent flags `131072` (`0x20000` = `FLAG_ACTIVITY_REORDER_TO_FRONT`), `PendingIntent.getActivity(…, flags 0)`. This is the "APK updated → OBB version/size now mismatched → click to re-download" path.

**`voicelib/ActivityReceiver`** (USER_PRESENT + PACKAGE_* events):

```java
a(ctx): Intent setClassName("com.ivona.tts", "com.ivona.ttslib.CustomSettingsService")
        .putExtra("upkgmon", true);  → queryIntentServices? startService : false
onReceive: if (!a(ctx) && retryThread == null) {
             uid = extras.getInt("android.intent.extra.UID", -1);
             if (uid != -1 && uid belongs to "com.ivona.tts")
                 new Thread( retry every 300 ms until a(ctx) succeeds ).start();
             return;
           }
           startService(setClassName("com.ivona.tts", "com.ivona.ttslib.engine.TTSServiceActivation"));
```

So the pack tells the engine "re-scan voice packages" (`upkgmon` → `IvonaPackagesInfo.c()` rebuild) and "activate the TTS service" whenever the device unlocks or packages change (`CustomSettingsService.java:30-34`, `IvonaPackagesInfo.c()`).

---

## 5. Kendra vs Amy — identical template or meaningful deltas?

Verified with `diff -rq` on both decompiled trees, `md5sum`, and manifest diff:

| Aspect | Verdict |
|---|---|
| `AndroidManifest.xml` | **Identical except** `package=`, `<application android:name>`, launcher `android:name`, `<receiver android:name>` (4 substitutions) |
| `com.ivona.tts.voicelib.*` (27 files) | **Byte-identical** (`diff -rq` exit 0) |
| `com.ivona.tts.commonlib.*` (11 files) | **Byte-identical** |
| Google libraries (downloader, licensing, analytics) | identical (same build) |
| `classes.dex` overall | different md5 — the Kendra dex additionally carries unused glue classes for `spa.esp.conchita` and `eng.usa.kendra`; Amy's lacks them (both dexes also contain sibling voices `joey, salli, gbr.amy/fra.celine/ita.giorgio/pol.maja` — template leftovers whose `R` references resolve to the single packaged `R` class; only manifest-selected classes matter) |
| Per-voice classes (`VoiceApp`, `IvonaVoice`, `CheckVoiceInstalled`, `UpdateReceiver`) | same code; only `CheckVoiceInstalled.a()` tag differs (`eng.usa.kendra.CheckVoiceInstalled` vs `eng.gbr.amy.CheckVoiceInstalled`) and `IvonaVoice.f()` returns `250` in **both** |
| `res/values/strings.xml` | differ in **exactly 7** default-locale strings (`app_name`, `textViewVoiceName`, `TAG`, `libvoice`, `textViewVoiceInfo`, `voice_welcome_text`, `app_icon`); `values-pl` differs in `app_name`/`textViewVoiceName`/`textViewVoiceInfo`; everything else (EULA, downloader states, buttons) identical |
| `libtiver.so`, `libttsivonavoice.so` | **identical** (same md5) — including libtiver's voice table, which contains rows for *both* voices |
| `libvoice_*.so` | different file + content (`libvoice_en_us_kendra.so` 3 085 840 B, `libvoice_en_gb_amy.so` 3 073 872 B) |
| Icons | per-voice `icon.png` (different md5; store `icon.png` matches the in-APK icon) |
| OBBs | different main payload (`CDXVvox_en_us_kendra` vs `CDXVvox_en_gb_amy`, different header word), different patch entry (`lang_en_us.dat` vs `lang_en_gb.dat`), different sizes (152 219 597 vs 149 905 560) |

**Conclusion:** the two APKs are outputs of one template; the meaningful deltas are the package name + four component names, 7 (+3 pl) strings, icon, the `libvoice_*.so`, and the two OBBs. Everything else is shared.

**What a new voice-pack author must change** (see also the checklist in §8): package name (must parse as `com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>`), the four manifest component names, `libvoice`/`app_name`/`textViewVoiceName`/`textViewVoiceInfo`/`voice_welcome_text`/`TAG`/`app_icon` strings (+pl variants), icon drawables, `libvoice_<…>.so`, both OBBs, and — critically — **rows inside `libtiver.so`** (§8), because the native table and the hardcoded `patch.199.` gate every install check.

---

## 6. Config files the engine parses

**The voice pack ships no config file.** The APK contains no `assets/`, no `res/xml`; the OBBs contain only the CDXV voice blob and `lang_*.dat` (§2.6). Everything XML-ish lives on the engine side:

1. **Embedded `ivona_config` XML in `libttsivona.so`** (engine). Strings: `/etc/ivona/ivona_config.xml`, `ivona_config`, element/section names **`global`, `packages`, `voice_data`, `voice_lib`, `lex_dir`**, plus a full XML writer/reader (`xml version="1.0" encoding="UTF-8"`, `<![CDATA[`, entity names …). It is exposed to Java through `ConfigXMLDataSet.getSettingsCfg()` / `getPackagesCfg()` JNI (`out/jadx_tts/.../config/ConfigXMLDataSet.java`). `IvonaPackagesInfo.b()` (`isoemn()==1`) selects the native-config package list; otherwise the CSV path is used. Likely pack-related values such as `<pkg>/lib/libvoice_*.so` (`voice_lib`) and OBB paths (`voice_data`) are configured here — **[INFERENCE: section contents not extracted; `/etc/ivona/…` is a desktop path and on Android the config appears compiled into the .so]**.
2. **`ivona_pkgs.csv`** — engine-private cache in `com.ivona.tts`'s files dir, written by `IvonaPackagesInfo.c()`:
   line 1 = rebuild timestamp; then per package `pkg;versionCode;<voicesApiVersion>` where the native `getVoicesApiVersion(String[] packages)` result is `apiVer;fstate;name;SDK` (Java parses `split[0]=apiVer, split[1]=fstate, split[2]=name, split[3]=SDK, split[4]=pkg…` at `IvonaPackagesInfo.java:51-64` and `:144+`). Reader tolerates ≥6 fields. The *display name* returned by native is unresolved (engine .so contains no voice names; the pack's `libtiver.so` table is the only nearby source of `"IVONA Kendra"` — **[INFERENCE]**).
3. **`/sdcard/ivona/`** — legacy directory (`IvonaPackagesInfo.a`, `com.ivona.tts.Ivona.a`), still deleted by `VoiceFiles.a()` on modern packs (§2.3); the engine's `libttsivona.so` also has `ivona/` + `Android/obb/` path fragments (**[INFERENCE]**: dual old/new lookup).

---

## 7. Billing / licensing / analytics in the voice pack

* **`com.android.vending.CHECK_LICENSE`** is declared (§1.1) and genuinely used: the expansion downloader performs Google Play licensing (LVL) with the RSA public key and AES salt from `VoiceDownloaderService.h()/i()` (§4.2) before it receives `FILE_URL/FILE_NAME/FILE_SIZE`. Failure surfaces as `state_failed_unlicensed` ("Download failed because you have not downloaded this app from Google Play"). Bundled licensing code: `com.google.android.vending.a.*` (`LicenseValidator`, `APKExpansionPolicy`, `AESObfuscator`, `PreferenceObfuscator`, AIDL `ILicensingService`/`ILicenseResultListener`).
* The pack does **not** declare `com.android.vending.BILLING` (the engine does). No in-app billing code in the pack.
* **Analytics: dead code.** `com.google.android.apps.analytics.*` (`AnalyticsReceiver` handling `com.android.vending.INSTALL_REFERRER`, SQLite `google_analytics.db` with `install_referrer`, `events`, `session`, `custom_variables` tables) is present in `classes.dex`, but the receiver is **not** registered in the manifest and no pack class references the package; no tracker ID (`UA-…`) or `google-analytics.com` endpoint exists in the dex.

---

## 8. Reimplementation checklist for a new voice pack

1. **Package name** `com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>` (engine parses `split[4..6]` as `Locale`), e.g. `com.ivona.tts.voicebeta.eng.usa.kendra`.
2. **Signer + UID**: `android:sharedUserId="com.ivona.ttsuser"`, signed with the engine's key (§1.1).
3. **Classes/manifest** (copy the template, rename): `<pkg>.VoiceApp extends AppLib` returning `R.string.libvoice`; `<pkg>.IvonaVoice extends voicelib.IvonaVoice` (MAIN/LAUNCHER, portrait, `Theme.NoTitleBar`, implements `a..e()` strings + `f()` size hint); `<pkg>.CheckVoiceInstalled extends voicelib.CheckVoiceInstalled` (action `com.ivona.tts.CHECK_VOICE_INSTALLED`, `Theme.NoDisplay`); `<pkg>.UpdateReceiver extends voicelib.UpdateReceiverLib`; both `ActivityReceiver` receivers; `VoiceDownloaderService`; permissions exactly as §1.1. (`.DownloadVoiceFilesService` may be omitted — it is a dead entry.) Keep the launcher class name literally `<pkg>.IvonaVoice` (§1.4-4).
4. **Strings**: `libvoice` = `<pkg>/lib/libvoice_<voice>.so` (must equal the native lib file name shipped under `lib/armeabi/`), `app_name`, `textViewVoiceName`, `textViewVoiceInfo`, `voice_welcome_text`, `TAG`, `app_icon` (one of the 13 codes the engine maps), `res_lang`; `current_eula_version=10`; `values-pl` translations optional.
5. **Native libs**: ship `libtiver.so` + `libttsivonavoice.so` (identical bytes are fine) + your `libvoice_<voice>.so`.
6. **Patch `libtiver.so`'s table** (48-byte rows, field layout in §A): add/update the row for your package — `main.<N>.<pkg>.obb` name with `<N>` of your choice, field[9] = **exact byte size** of your main OBB, field[6] = exact size of your `libvoice_*.so`, locale/name/message fields. Without a matching row the size gate uses the all-zero terminator row, `stat()` fails, and `checkFiles` returns 1 forever → the pack never reports installed **[INFERENCE: terminator-row behavior follows the decompiled loop]**.
7. **OBBs** at `<sdcard>/Android/obb/<pkg>/`: `main.<N>.<pkg>.obb` = CDXV container whose header name matches your voice (`vox_<lang>_<ctry>_<voice>` style); `patch.199.<pkg>.obb` = zip containing `lang_<…>.dat` — **the `patch.199.` prefix is hardcoded**, so use expansion version 199 for the patch (main's `<N>` is free). No checksums are validated — size equality is the gate.
8. **Legacy table** `voicelib/q.java` row (optional; only deletes pre-OBB files under `/sdcard/ivona/`).
9. **Engine registry**: ensure your package appears to the engine — it will be enumerated via the shared UID; add it to `com.ivona.ttslib.packages.c`'s static map (engine side) for a display-name fallback if the native `getVoicesApiVersion` path does not know it **[INFERENCE]**; the engine also expects `pack.versionCode == engine.versionCode` when it relaunches a not-fully-installed pack (§3.4).
10. **Play distribution** (only for real store installs): expansion files must be registered so LVL returns `FILE_NAME/FILE_SIZE/FILE_URL`; for sideload reimplementation, pre-place the OBBs — with files present and size-exact, the downloader returns "0" and is never started.

---

## Appendix A — `libtiver.so` voice table (decoded)

Location `.data.rel.ro.local` vaddr 0x1d538 (file 0x1c538), stride 48 bytes, 42 entries + zero terminator. Field layout (dword indices):

| # | meaning | Kendra row | Amy row |
|---|---|---|---|
| 0 | ISO639-2 language | `eng` | `eng` |
| 1 | ISO3166-3 country | `USA` | `GBR` |
| 2 | voice short name | `kendra` | `amy` |
| 3 | display name | `IVONA Kendra` | `IVONA Amy` |
| 4 | package name (lookup key) | `com.ivona.tts.voicebeta.eng.usa.kendra` | `com.ivona.tts.voicebeta.eng.gbr.amy` |
| 5 | voice lib file | `libvoice_en_us_kendra.so` | `libvoice_en_gb_amy.so` |
| 6 | voice-lib byte size (verified vs APK) | `3085840` | `3073872` |
| 7 | second per-voice size (meaning unresolved) | `3099004` | `3086172` |
| 8 | main OBB file name | `main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb` | `main.199.com.ivona.tts.voicebeta.eng.gbr.amy.obb` |
| 9 | expected main-OOB byte size (verified) | `152219597` | `149905560` |
| 10 | lexicon file | `english.lex` | `english.lex` |
| 11 | trial-expired message (localized per row) | `The trial period of the IVONA voice has expired. …` | same |

`<N>` in field[8] varies per voice in this table: `199` (kendra, amy, gwyneth cym+eng, marlene, nicole, conchita, penelope, celine, giorgio, carmen), `183` (salli, maja), `422` (all newer voices). Other strings in `libtiver.so`: log tag `IVONAVOICE`, `Android/obb/`, `patch.199.`, `.obb`, build stamp `20130201_150739`, `unzip 1.01 Copyright 1998-2004 Gilles Vollant`.

## Appendix B — quick reference: every literal string crossing a pack↔engine boundary

* Manifest action: `com.ivona.tts.CHECK_VOICE_INSTALLED` (pack, legacy).
* Extras: `checkVoice` / `checkVoiceResult` (legacy); `VoicePackage`, `welcome_text`, `app_name`, `voice_info`, `app_icon`, `dont_return_to_gui` (live, pack→`com.ivona.tts/com.ivona.ttslib.IvonaGui`); `upkgmon` (pack→`com.ivona.tts/com.ivona.ttslib.CustomSettingsService`); `IvonaLibvoices` (set by pack, unused by engine); `EPI` (downloader PendingIntent); `android.intent.extra.UID` (broadcasts).
* Components the pack addresses: `com.ivona.tts` + `com.ivona.ttslib.CustomSettingsService`, `com.ivona.ttslib.engine.TTSServiceActivation`, `com.ivona.ttslib.CheckVoiceData`, `com.ivona.ttslib.IvonaGui`, `com.google.tts.TextToSpeechSettings`.
* Protocol strings: `Check voice installed`, `Voice is installed`, `Voice is not installed`.
* Downloader: action `android.intent.action.DOWNLOAD_WAKEUP`, MIME `application/vnd.android.obb`, extras `FILE_URL<n>/FILE_NAME<n>/FILE_SIZE<n>` (Play-side).
* Resource keys: `libvoice`, `app_icon`, `TAG`, `textViewVoiceName`, `textViewVoiceInfo`, `voice_welcome_text`, `%file_size%`, prefs `ivona_package`/`agr_int_ver`, engine cache `ivona_pkgs.csv`.

## Appendix C — uncertainty log

1. **[INFERENCE]** exact `struct stat` field mapping inside the decompiled `libtiver` size check (Ghidra field labels are shifted; size-equality itself is verified against real OBB sizes).
2. **[INFERENCE]** meaning of table field[7] and of CDXV header words (`0x5622`=22050 sample rate, crc/timestamp).
3. **[INFERENCE]** `english.lex` location/lifecycle (engine `lex_dir` config?), `ISEF` header meaning.
4. **[INFERENCE]** how engine native `getVoicesApiVersion` obtains a package's display name (`libtiver.so` table vs manifest label vs APK resources) — engine .so contains no voice names.
5. **[INFERENCE]** whether the engine `dlopen`s `/data/data/<pkg>/lib/libtiver.so` (string evidence only) and whether `isoemn()==1` (embedded `ivona_config`) or the CSV path is active on-device.
6. **[INFERENCE]** exact original loop in `RequestCode.a(String)` (jadx collapsed it; single enum value makes it moot).
7. Download/licensing hosts are not present in any artifact (Play-provided at runtime).
