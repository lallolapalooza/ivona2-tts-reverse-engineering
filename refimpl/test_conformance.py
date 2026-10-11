"""Conformance tests for the IVONA 2 reference implementation.

Run with::

    python3 -m unittest discover -s refimpl -v

Every test encodes a fact documented in the analysis reports (each docstring
cites the report + section).  Tests exercise the **real** artifacts shipped in
this repository (APKs, OBBs, unlocked ``lang_*.dat`` files, native libraries)
wherever a machine-checkable fact exists; facts that are not machine-checkable
are listed in ``README.md`` rather than faked here.
"""

from __future__ import annotations

import os
import struct
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cdxv          # noqa: E402
import license as lic  # noqa: E402
import marks         # noqa: E402
import params        # noqa: E402
import voices        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KENDRA_APK_DIR = os.path.join(
    ROOT,
    "IVONA 2",
    "IVONA Kendra US English beta_v1.6.23.422_apkfab.com",
    "Android",
    "obb",
    "com.ivona.tts.voicebeta.eng.usa.kendra",
)
AMY_APK_DIR = os.path.join(
    ROOT,
    "IVONA 2",
    "com.ivona.tts.voicebeta.eng.gbr.amy_1623422_apkplz.net",
    "Android",
    "obb",
    "com.ivona.tts.voicebeta.eng.gbr.amy",
)
KENDRA_PKG = "com.ivona.tts.voicebeta.eng.usa.kendra"
AMY_PKG = "com.ivona.tts.voicebeta.eng.gbr.amy"

MAIN_KENDRA = os.path.join(KENDRA_APK_DIR, f"main.199.{KENDRA_PKG}.obb")
MAIN_AMY = os.path.join(AMY_APK_DIR, f"main.199.{AMY_PKG}.obb")
PATCH_KENDRA = os.path.join(KENDRA_APK_DIR, f"patch.199.{KENDRA_PKG}.obb")
PATCH_AMY = os.path.join(AMY_APK_DIR, f"patch.199.{AMY_PKG}.obb")

BRIDGE_SO = os.path.join(ROOT, "out", "tts", "lib", "armeabi", "libttsivona.so")
VOICE_LIB = os.path.join(ROOT, "out", "libs", "kendra", "libttsivonavoice.so")
CERT_DUMP = os.path.join(ROOT, "out", "certs", "ivona_certificate_decoded.txt")
TABLE_JSON = os.path.join(ROOT, "scripts", "table_full.json")
LANG_US = os.path.join(ROOT, "out", "obb", "lang_en_us.dat")
LANG_GB = os.path.join(ROOT, "out", "obb", "lang_en_gb.dat")

_VALIDATION_CACHE = {}


def validation(path):
    """Run (and cache) the full invariant pass for ``path``."""
    if path not in _VALIDATION_CACHE:
        with cdxv.OBBReader(path) as r:
            _VALIDATION_CACHE[path] = r.validate()
    return _VALIDATION_CACHE[path]


def reader(path):
    return cdxv.OBBReader(path)


# ===========================================================================
# CDXV container (report_obb_format.md)
# ===========================================================================
class TestCDXVHeader(unittest.TestCase):
    def _check(self, path, name, checksum, index_off, index_len,
               a, b, c, d, e):
        with reader(path) as r:
            h = r.header
            self.assertEqual(h.magic, b"CDXV")                       # §2 magic
            self.assertEqual(h.name, name)                           # §2 @0x04
            self.assertEqual(h.sample_rate, 22050)                   # §2 @0x24
            self.assertEqual(h.format_id, 14)                        # §2 @0x28
            self.assertIn(h.format_id, cdxv.ACCEPTED_FORMAT_IDS)     # §4.5 of brief
            self.assertEqual(h.checksum, checksum)                   # §2 @0x2C
            self.assertEqual(h.index_pair, (index_off, index_len))   # §2 @0x30
            self.assertEqual(h.payload_pair[1], 0)                   # §2 @0x3C
            self.assertEqual(h.section_pair("A"), a)                 # §2 @0x40
            self.assertEqual(h.section_pair("B"), b)                 # §2 @0x48
            self.assertEqual(h.section_pair("C"), c)                 # §2 @0x50
            self.assertEqual(h.section_pair("D"), d)                 # §2 @0x58
            self.assertEqual(h.section_pair("E"), e)                 # §2 @0x60
            self.assertEqual(h.index_pair[0], 0x68)                  # §2 index at 0x68

    def test_header_kendra(self):
        """report_obb_format.md §2/§12: Kendra header fields."""
        self._check(
            MAIN_KENDRA, "vox_en_us_kendra", 1333557784, 104, 3415928,
            (0x341FE0, 32020), (0x349CF8, 1673980), (0x4E27F8, 15371676),
            (0x138B598, 4860925), (0x182E198, 1856),
        )

    def test_header_amy(self):
        """report_obb_format.md §2/§12: Amy header fields."""
        self._check(
            MAIN_AMY, "vox_en_gb_amy", 1334671314, 104, 3238776,
            (0x316BE0, 35440), (0x31F650, 1586732), (0x4A2C80, 14574492),
            (0x1289020, 4709055), (0x1706AE0, 1984),
        )


class TestCDXVIndex(unittest.TestCase):
    def test_counts_and_nulls(self):
        """report_obb_format.md §3/§12: N=426991/404847, nulls 8496/8164."""
        for path, n, nulls in ((MAIN_KENDRA, 426991, 8496), (MAIN_AMY, 404847, 8164)):
            with reader(path) as r:
                self.assertEqual(r.n_entries, n)
                self.assertEqual(r.n_null, nulls)
                self.assertEqual(r.header.index_pair[1] // 8, n)

    def test_contiguity_and_eof(self):
        """report_obb_format.md §3: records tile [first_offset, EOF) contiguously."""
        for path in (MAIN_KENDRA, MAIN_AMY):
            v = validation(path)
            self.assertEqual(v.contiguity_anomalies, [])
            self.assertEqual(v.last_record_end, v.file_size)

    def test_first_entry(self):
        """report_obb_format.md §3: first entry offset 0x7FABF03 (Kendra)."""
        with reader(MAIN_KENDRA) as r:
            self.assertEqual(r.index[0].offset, 0x7FABF03)
            self.assertEqual(r.index[0].length, 0x4C)
            self.assertEqual(r.index[1].offset, r.index[0].offset + r.index[0].length)


class TestCDXVSections(unittest.TestCase):
    def test_section_c_is_36n(self):
        """report_obb_format.md §6: len(C) == 36*N exactly."""
        for path in (MAIN_KENDRA, MAIN_AMY):
            v = validation(path)
            self.assertTrue(v.section_c_len_ok)
            self.assertEqual(v.section_c_actual_len, v.section_c_expected_len)

    def test_diphone_counts(self):
        """report_obb_format.md §4/§12: 1601/1772 diphones, sum(count) == len(B)/4."""
        for path, count, total in ((MAIN_KENDRA, 1601, 418495), (MAIN_AMY, 1772, 396683)):
            v = validation(path)
            self.assertEqual(v.diphone_count, count)
            self.assertEqual(v.diphone_sum_count, total)
            self.assertEqual(v.section_b_len_u32, total)
            self.assertTrue(v.diphone_sum_matches_b)
            self.assertEqual(v.diphone_chain_anomalies, 0)
            self.assertEqual(v.diphone_names_without_nul, 0)

    def test_b_is_permutation_of_non_null_ids(self):
        """report_obb_format.md §5: B is an exact permutation of non-null ids."""
        for path in (MAIN_KENDRA, MAIN_AMY):
            v = validation(path)
            self.assertTrue(v.b_is_permutation)
            self.assertEqual(v.b_duplicates, 0)
            self.assertEqual(v.b_invalid_ids, 0)
            self.assertEqual(v.missing_ids, 0)

    def test_first_diphone_record(self):
        """report_obb_format.md §4 hexdump: record 0 == 'aa-aa' start=0 count=6."""
        with reader(MAIN_KENDRA) as r:
            d = r.diphones()
            self.assertEqual((d[0].name, d[0].start, d[0].count), ("aa-aa", 0, 6))
            self.assertEqual((d[1].name, d[1].start, d[1].count), ("aa-ah", 6, 3))


class TestCDXVPhonemes(unittest.TestCase):
    def test_counts(self):
        """report_obb_format.md §8/§12: 58 phonemes (Kendra) / 62 (Amy)."""
        self.assertEqual(validation(MAIN_KENDRA).phoneme_count, 58)
        self.assertEqual(validation(MAIN_AMY).phoneme_count, 62)

    def test_first_is_boundary_symbol(self):
        """report_obb_format.md §8: first record is '0'."""
        for path in (MAIN_KENDRA, MAIN_AMY):
            with reader(path) as r:
                self.assertEqual(r.phonemes()[0], "0")

    def test_amy_extra_phonemes(self):
        """report_obb_format.md §8: Amy adds {eax, iax, o, uax}."""
        with reader(MAIN_KENDRA) as r:
            k = set(r.phonemes())
        with reader(MAIN_AMY) as r:
            a = set(r.phonemes())
        self.assertEqual(a - k, {"eax", "iax", "o", "uax"})
        self.assertTrue({"pau", "ax", "hh"} <= k)


class TestCDXVUnitRecords(unittest.TestCase):
    def test_record_invariants(self):
        """report_obb_format.md §9: len==2N+12, ramp monotone, windows inside gap."""
        for path in (MAIN_KENDRA, MAIN_AMY):
            v = validation(path)
            self.assertEqual(v.record_size_violations, 0)
            self.assertEqual(v.ramp_violations, 0)
            self.assertEqual(v.window_outside_gap, 0)
            # every window lies inside the gap and the union ends exactly at the
            # first index record (report_obb_format.md §8).
            self.assertEqual(v.min_gap_offset, v.gap_start)
            self.assertEqual(v.max_window_end, v.gap_end)

    def test_statistics(self):
        """report_obb_format.md §9/§12: N ranges, sum(N), gap stats."""
        kv = validation(MAIN_KENDRA)
        av = validation(MAIN_AMY)
        self.assertEqual(kv.N_range, (3, 130))
        self.assertEqual(kv.sum_N, 6662123)
        self.assertEqual(av.N_range, (4, 97))
        self.assertEqual(av.sum_N, 7267240)
        self.assertEqual(kv.distinct_gap_offsets, 324820)
        self.assertEqual(av.distinct_gap_offsets, 304687)
        # summed window lengths massively overlap the gap (report §8).
        self.assertEqual(kv.sum_gap_lengths, 361352490)
        self.assertEqual(av.sum_gap_lengths, 346537077)

    def test_first_record_fields(self):
        """report_obb_format.md §9 hexdump: first Kendra record values."""
        with reader(MAIN_KENDRA) as r:
            rec = r.parse_unit_record(r.index[0].offset, r.index[0].length)
            self.assertEqual(rec.N, 32)
            self.assertEqual(rec.size, 76)
            self.assertEqual(rec.ramp[-1], 0x11B9)      # 4537
            self.assertEqual(rec.Y, 0x0B84)             # 2948
            self.assertEqual(rec.gap_offset, 0x0182E8D8)
            self.assertEqual(rec.gap_length, 0x23E)     # 574

    def test_overall_ok(self):
        """All documented CDXV invariants hold on both real files."""
        self.assertTrue(validation(MAIN_KENDRA).ok)
        self.assertTrue(validation(MAIN_AMY).ok)


# ===========================================================================
# OBB / patch byte sizes and lang_*.dat (report_obb_format.md §1/§11, brief §1)
# ===========================================================================
class TestObbArtifacts(unittest.TestCase):
    def test_main_obb_sizes(self):
        """brief §1: main.199 sizes 152 219 597 (Kendra) / 149 905 560 (Amy)."""
        self.assertEqual(os.path.getsize(MAIN_KENDRA), 152219597)
        self.assertEqual(os.path.getsize(MAIN_AMY), 149905560)

    def test_patch_sizes(self):
        """report_obb_format.md §1/§11: both patches are 74 861 bytes."""
        self.assertEqual(os.path.getsize(PATCH_KENDRA), 74861)
        self.assertEqual(os.path.getsize(PATCH_AMY), 74861)

    def test_patch_zip_contents(self):
        """report_obb_format.md §11: one entry, uncompressed 74 668, CRC32, date."""
        expected = [
            (PATCH_KENDRA, "lang_en_us.dat", "6cc78a8f"),
            (PATCH_AMY, "lang_en_gb.dat", "5dbfd93c"),
        ]
        for path, name, crc in expected:
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                self.assertEqual(len(infos), 1)
                info = infos[0]
                self.assertEqual(info.filename, name)
                self.assertEqual(info.file_size, 74668)
                # report_obb_format.md §11 prints "74 863" for the deflated size;
                # the real ZIP central directory holds 74 683 (digits transposed
                # in the report).  The artifact is ground truth.
                self.assertEqual(info.compress_size, 74683)
                self.assertEqual(f"{info.CRC:08x}", crc)
                self.assertEqual(
                    (info.date_time[:3], info.date_time[3:]),
                    ((2013, 2, 1), (18, 9, 26)),
                )

    def test_lang_dat_header(self):
        """report_obb_format.md §11: 'ISEF' + BE u32 1 + constant 50 99 2b cc."""
        for path in (LANG_US, LANG_GB):
            with open(path, "rb") as fh:
                data = fh.read()
            self.assertEqual(len(data), 74668)
            self.assertEqual(data[:4], b"ISEF")
            self.assertEqual(struct.unpack_from(">I", data, 4)[0], 1)
            self.assertEqual(data[8:12], bytes([0x50, 0x99, 0x2B, 0xCC]))

    def test_lang_dat_differs_after_12(self):
        """report_obb_format.md §11: US/GB identical only in bytes 0-11."""
        with open(LANG_US, "rb") as fh:
            us = fh.read()
        with open(LANG_GB, "rb") as fh:
            gb = fh.read()
        self.assertEqual(us[:12], gb[:12])
        self.assertNotEqual(us[12:], gb[12:])


# ===========================================================================
# Package discovery / naming / size gates (report_libtiver.md, report_engine_app.md §5)
# ===========================================================================
class TestVoicePackageGrammar(unittest.TestCase):
    def test_parse(self):
        """report_engine_app.md §5.6: 7 dot parts -> locale triple."""
        vp = voices.parse_package_name("com.ivona.tts.voicebeta.eng.gbr.amy")
        self.assertEqual(vp.locale, ("eng", "gbr", "amy"))
        vp2 = voices.parse_package_name("com.ivona.tts.voicebeta.eng.usa.kendra")
        self.assertEqual(vp2.locale, ("eng", "usa", "kendra"))

    def test_rejects_malformed(self):
        for bad in (
            "com.ivona.tts.voicebeta.eng.gbr",
            "com.ivona.tts.voicebeta.eng.gbr.amy.extra",
            "com.other.tts.voicebeta.eng.gbr.amy",
        ):
            with self.assertRaises(voices.VoiceError):
                voices.parse_package_name(bad)

    def test_selection_file_name(self):
        """report_engine_app.md §5.7: '.<iso3lang>_<iso3country>' lowercased."""
        self.assertEqual(voices.selection_file_name("eng", "GBR"), ".eng_gbr")
        self.assertEqual(voices.selection_file_name("spa", "USA"), ".spa_usa")

    def test_probe_order(self):
        """report_libtiver.md §5: '<sdcard>/ivona/' then '<sdcard>/Android/obb/'."""
        self.assertEqual(voices.DATA_ROOT_PROBE_ORDER, ("ivona/", "Android/obb/"))

    def test_data_location_fold(self):
        """report_libtiver.md §5: 1=/ivona/, 2=/Android/obb/, 0=none."""
        self.assertEqual(voices.resolve_data_location([0, 1]), 1)
        self.assertEqual(voices.resolve_data_location([1, 0]), 2)
        self.assertEqual(voices.resolve_data_location([1, 1]), 0)


class TestObbNaming(unittest.TestCase):
    def test_main_name(self):
        """report_libtiver.md §6: main.<N>.<pkg>.obb."""
        self.assertEqual(
            voices.main_obb_name(199, AMY_PKG), f"main.199.{AMY_PKG}.obb"
        )

    def test_patch_always_199(self):
        """report_libtiver.md §3.1/§7.1: patch version is hardcoded 199."""
        self.assertEqual(
            voices.patch_obb_name(AMY_PKG), f"patch.199.{AMY_PKG}.obb"
        )
        self.assertEqual(voices.PATCH_VERSION, 199)

    def test_obb_path(self):
        self.assertEqual(
            voices.obb_path("/sdcard/Android/obb/", AMY_PKG, "x.obb"),
            f"/sdcard/Android/obb/{AMY_PKG}/x.obb",
        )


class TestSizeGate(unittest.TestCase):
    def test_real_sizes_pass(self):
        """brief §1 / report_libtiver.md §7.1: exact byte-size gate."""
        self.assertTrue(voices.size_gate(MAIN_KENDRA, 152219597))
        self.assertTrue(voices.size_gate(MAIN_AMY, 149905560))

    def test_wrong_size_fails(self):
        self.assertFalse(voices.size_gate(MAIN_KENDRA, 152219596))
        self.assertFalse(voices.size_gate(os.path.join(ROOT, "does-not-exist"), 1))

    def test_check_package(self):
        """report_libtiver.md §3: table lookup + size gate -> 0."""
        rows = voices.load_table(TABLE_JSON)
        base = os.path.join(ROOT, "IVONA 2", "IVONA Kendra US English "
                            "beta_v1.6.23.422_apkfab.com", "Android", "obb") + os.sep
        self.assertEqual(voices.check_package(KENDRA_PKG, base, rows), 0)
        self.assertEqual(voices.check_package("com.ivona.tts.voicebeta.eng.gbr.amy", base, rows), 1)


class TestLibtiverTable(unittest.TestCase):
    def setUp(self):
        self.rows = voices.load_table(TABLE_JSON)

    def test_row_count(self):
        """report_libtiver.md §4: 42 hardcoded table rows."""
        self.assertEqual(len(self.rows), 42)

    def test_terminator_not_in_table(self):
        """The decoded table excludes the all-zero terminator row (§4)."""
        self.assertTrue(all(r.package for r in self.rows))

    def test_known_rows(self):
        """report_libtiver.md §4 rows 8/16 (amy/kendra)."""
        k = voices.find_row(self.rows, KENDRA_PKG)
        a = voices.find_row(self.rows, AMY_PKG)
        self.assertEqual((k.lang, k.country, k.name, k.display_name),
                         ("eng", "USA", "kendra", "IVONA Kendra"))
        self.assertEqual(k.obb_size, 152219597)
        self.assertEqual(k.main_obb, f"main.199.{KENDRA_PKG}.obb")
        self.assertEqual((a.lang, a.country, a.name, a.display_name),
                         ("eng", "GBR", "amy", "IVONA Amy"))
        self.assertEqual(a.obb_size, 149905560)
        self.assertEqual(a.main_obb, f"main.199.{AMY_PKG}.obb")

    def test_obb_versions(self):
        """report_libtiver.md §4: N in {183, 199, 422}."""
        versions = {r.obb_version for r in self.rows}
        self.assertTrue(versions <= set(voices.MAIN_VERSIONS))
        self.assertEqual({r.name for r in self.rows if r.obb_version == 183},
                         {"salli", "maja"})

    def test_main_obb_name_matches_row(self):
        """report_libtiver.md §7.1: main_obb_name(N, pkg) == table field."""
        for r in self.rows:
            self.assertEqual(voices.main_obb_name(r.obb_version, r.package), r.main_obb)

    def test_voice_lib_sizes_match_disk(self):
        """report_libtiver.md §4 field [6]: voice-lib size verified on disk."""
        for pkg_dir, lib, size in (
            (os.path.join(ROOT, "out", "libs", "kendra"), "libvoice_en_us_kendra.so", 3085840),
            (os.path.join(ROOT, "out", "libs", "amy"), "libvoice_en_gb_amy.so", 3073872),
        ):
            self.assertEqual(os.path.getsize(os.path.join(pkg_dir, lib)), size)


class TestVStruct(unittest.TestCase):
    def test_gate_accepts_reference_struct(self):
        """report_libtiver.md §2/§5: the real struct {20,2,stamp,48,acc} passes."""
        s = voices.VStruct(20, 2, "20130201_150739", 48, 0)
        self.assertTrue(voices.v_struct_gate(s))

    def test_gate_rejects_each_failing_field(self):
        """report_libtiver.md §5: gates are abi>0x13, stride>0x2f, apiVer<3."""
        self.assertFalse(voices.v_struct_gate(voices.VStruct(0x13, 2, "s", 48)))
        self.assertFalse(voices.v_struct_gate(voices.VStruct(20, 2, "s", 0x2F)))
        self.assertFalse(voices.v_struct_gate(voices.VStruct(20, 3, "s", 48)))

    def test_build_stamp(self):
        """report_libtiver.md §2: struct[2] == '20130201_150739'."""
        self.assertEqual(voices.VStruct(20, 2, "20130201_150739", 48).build_stamp,
                         "20130201_150739")

    def test_accessor_limit(self):
        """report_libtiver.md §2: entry(i) valid for i <= 43 only."""
        self.assertEqual(voices.accessor_entry_index(0), 0)
        self.assertEqual(voices.accessor_entry_index(43), 43)
        self.assertIsNone(voices.accessor_entry_index(44))


class TestVoiceReport(unittest.TestCase):
    def test_format(self):
        """report_libtiver.md §5: '%d;%d;' + name + ';' + stamp + ';%d'."""
        self.assertEqual(
            voices.format_voice_report(2, 0, "IVONA Kendra", "20130201_150739", 2),
            "2;0;IVONA Kendra;20130201_150739;2",
        )

    def test_roundtrip(self):
        r = voices.parse_voice_report("2;0;IVONA Amy;20130201_150739;2")
        self.assertEqual((r.api_version, r.fstate, r.display_name, r.stamp, r.data_location),
                         (2, 0, "IVONA Amy", "20130201_150739", 2))
        self.assertEqual(r.to_string(), "2;0;IVONA Amy;20130201_150739;2")

    def test_five_fields(self):
        with self.assertRaises(voices.VoiceError):
            voices.parse_voice_report("2;0;name;stamp")


class TestPackagesCsv(unittest.TestCase):
    def test_columns(self):
        """report_engine_app.md §5.3: 7 ';'-separated fields per data line."""
        self.assertEqual(
            voices.CSV_COLUMNS,
            ("package", "versionCode", "apiVersion", "fstate", "displayName",
             "stamp", "dataLocation"),
        )

    def test_roundtrip(self):
        import tempfile

        rows = [
            voices.CacheRow(KENDRA_PKG, 422, 2, 0, "IVONA Kendra",
                            "20130201_150739", 2),
        ]
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ivona_pkgs.csv")
            voices.write_packages_csv(p, 1700000000000, rows)
            ts, got = voices.read_packages_csv(p)
        self.assertEqual(ts, 1700000000000)
        self.assertEqual(got, rows)

    def test_short_lines_ignored(self):
        """report_engine_app.md §5.3: reader consumes lines with >= 6 fields."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ivona_pkgs.csv")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("123\n")
                fh.write("a;b;c\n")  # < 6 fields -> ignored
                fh.write(f"{KENDRA_PKG};422;2;0;IVONA Kendra;20130201_150739;2\n")
            ts, rows = voices.read_packages_csv(p)
        self.assertEqual(ts, 123)
        self.assertEqual(len(rows), 1)


# ===========================================================================
# Embedded certificate (report_ttsivona.md §8, brief §4.4)
# ===========================================================================
class TestLicense(unittest.TestCase):
    def setUp(self):
        with open(BRIDGE_SO, "rb") as fh:
            self.so = fh.read()

    def test_decode_length(self):
        """brief §4.4: decoded length == 1798."""
        self.assertEqual(len(lic.decode_certificate(self.so)), 1798)

    def test_decode_matches_reference_dump(self):
        """brief §4.4: decode == out/certs/ivona_certificate_decoded.txt."""
        decoded = lic.decode_certificate(self.so)
        with open(CERT_DUMP, "rb") as fh:
            self.assertEqual(decoded, fh.read())

    def test_attributes(self):
        """brief §4.4: certificate attribute values."""
        cert = lic.decode_and_parse(BRIDGE_SO)
        self.assertEqual(cert.attributes["Product"], "IVONA")
        self.assertEqual(cert.attributes["Certificate-ID"], "a1169787")
        self.assertEqual(cert.attributes["Num-threads"], "UNLIMITED")
        self.assertEqual(cert.attributes["Thread-speed"], "UNLIMITED")
        self.assertEqual(cert.attributes["Expiration-date"], "NEVER")
        self.assertEqual(cert.attributes["Voices"], "ALL")
        self.assertEqual(cert.attributes["Extension-SSML"], "TRUE")

    def test_semantic_flags(self):
        cert = lic.decode_and_parse(BRIDGE_SO)
        self.assertTrue(cert.num_threads_unlimited)
        self.assertTrue(cert.thread_speed_unlimited)
        self.assertTrue(cert.expiration_never)
        self.assertTrue(cert.voices_all)
        self.assertTrue(cert.ssml_extension)

    def test_signature_block(self):
        """brief §4.4: 14 lines / 1040 hex chars = 520 bytes (RSA-4096)."""
        cert = lic.decode_and_parse(BRIDGE_SO)
        self.assertEqual(len(cert.signature_hex), 1040)
        self.assertEqual(len(cert.signature_bytes), 520)


# ===========================================================================
# Speech marks (report_ttsivona.md §10, report_engine_synth.md §4.2/§4.3)
# ===========================================================================
class TestMarks(unittest.TestCase):
    def test_ownership_table(self):
        """report_engine_synth.md §4.2: table at 0x14bfc8 == {0,1,1,0,1}."""
        with open(VOICE_LIB, "rb") as fh:
            data = fh.read()
        self.assertEqual(marks.read_ownership_table(data), (0, 1, 1, 0, 1))

    def test_type_names(self):
        """report_engine_api.md §6.3: the five SpeechMark constants, in order."""
        with open(BRIDGE_SO, "rb") as fh:
            data = fh.read()
        self.assertEqual(
            marks.read_type_names(data),
            ("TYPE_PHONEME", "TYPE_WORD", "TYPE_SENTENCE", "TYPE_SSML", "TYPE_VISEME"),
        )

    def test_record_parse(self):
        """report_ttsivona.md §10: 20-byte record {type, name*, start, end, sample}."""
        raw = struct.pack("<IIiii", 3, 0xDEADBEEF, 10, 25, 4096)
        self.assertEqual(len(raw), marks.MARK_RECORD_SIZE)
        m = marks.parse_mark(raw)
        self.assertEqual(m.type, 3)
        self.assertEqual(m.name_ptr, 0xDEADBEEF)
        self.assertEqual((m.start_text_offset, m.end_text_offset, m.sample_offset),
                         (10, 25, 4096))
        self.assertIsNone(m.name)
        self.assertEqual(m.android_constant, "TYPE_SSML")

    def test_record_pack_unpack_roundtrip(self):
        raw = struct.pack("<IIiii", 1, 0, -1, -1, 12345)
        m = marks.parse_mark(raw)
        self.assertEqual((m.type, m.start_text_offset, m.end_text_offset, m.sample_offset),
                         (1, -1, -1, 12345))

    def test_null_name_maps_to_none(self):
        """report_ttsivona.md §10: name pointer 0 -> Java null."""
        raw = struct.pack("<IIiii", 2, 0, 0, 0, 0)
        self.assertIsNone(marks.parse_mark(raw).name)

    def test_name_resolver(self):
        raw = struct.pack("<IIiii", 3, 0x100, 0, 0, 0)
        m = marks.parse_mark(raw, resolve_name=lambda ptr: "hello")
        self.assertEqual(m.name, "hello")

    def test_bitmask(self):
        """brief §6: bit N of GENERATE_MARKS enables type N."""
        self.assertTrue(marks.mark_enabled(0b00100, 2))
        self.assertFalse(marks.mark_enabled(0b00100, 3))
        self.assertEqual(marks.enabled_types(0b10110), (1, 2, 4))
        self.assertEqual(marks.mask_for_types([1, 3]), 0b1010)

    def test_ownership_rule(self):
        """report_engine_synth.md §4.2: 1 => alias/never free, 0 => heap copy."""
        table = (0, 1, 1, 0, 1)
        self.assertFalse(marks.owns_name(0, table))
        self.assertTrue(marks.owns_name(1, table))
        self.assertTrue(marks.owns_name(2, table))
        self.assertFalse(marks.owns_name(3, table))
        self.assertTrue(marks.owns_name(4, table))
        with self.assertRaises(marks.MarkError):
            marks.owns_name(5, table)

    def test_iter_marks(self):
        buf = b"".join(
            struct.pack("<IIiii", t, 0, t, t + 1, t * 100)
            for t in range(5)
        )
        got = list(marks.iter_marks(buf, 5))
        self.assertEqual([m.type for m in got], [0, 1, 2, 3, 4])
        self.assertEqual([m.sample_offset for m in got], [0, 100, 200, 300, 400])

    def test_type_table(self):
        """report_engine_api.md §6.3: engine type -> Android constant."""
        self.assertEqual(marks.MARK_TYPES[0][1], "TYPE_PHONEME")
        self.assertEqual(marks.MARK_TYPES[4][1], "TYPE_VISEME")


# ===========================================================================
# Voice parameters (report_engine_api.md §8)
# ===========================================================================
class TestParams(unittest.TestCase):
    def test_table_keys(self):
        """report_engine_api.md §8: the 16 command-table keys."""
        self.assertEqual(
            set(params.PARAM_TABLE),
            {"volume", "dur_stretch", "pitch_stretch", "contrast", "quality",
             "responsiveness", "sentence_break", "paragraph_break",
             "max_sentence_length", "max_word_length", "text_encoding",
             "base_uri", "input_type", "fetch_function", "fetch_user_data",
             "dict_insert_id"},
        )

    def test_grammar(self):
        """report_engine_api.md §8: 'set|get:KEY[:min|max|def]'."""
        self.assertEqual(params.parse_command("set:volume"), ("set", "volume", None))
        self.assertEqual(params.parse_command("get:quality"), ("get", "quality", None))
        self.assertEqual(params.parse_command("set:dur_stretch:max"),
                         ("set", "dur_stretch", "max"))
        self.assertEqual(params.parse_command("get:volume:def"),
                         ("get", "volume", "def"))

    def test_unknown_command_errors(self):
        """report_engine_api.md §8: unknown cmd/KEY/qualifier -> errno 8."""
        for bad in ("frob:volume", "set:nope", "set:volume:wat", "volume"):
            with self.assertRaises(params.ParamError) as cm:
                params.parse_command(bad)
            self.assertEqual(cm.exception.errno, 8)

    def test_int_ranges(self):
        """report_engine_api.md §8 value ranges -> errno 6 when out of range."""
        params.validate_int_value("contrast", 0)
        params.validate_int_value("contrast", 1)
        with self.assertRaises(params.ParamError):
            params.validate_int_value("contrast", 2)
        params.validate_int_value("quality", 1)
        params.validate_int_value("quality", 10)
        with self.assertRaises(params.ParamError):
            params.validate_int_value("quality", 11)
        params.validate_int_value("sentence_break", 60000)
        with self.assertRaises(params.ParamError):
            params.validate_int_value("sentence_break", 60001)
        params.validate_int_value("max_sentence_length", 0x7FFFFFFF)
        with self.assertRaises(params.ParamError):
            params.validate_int_value("max_sentence_length", 0)

    def test_float_key_encoding_range(self):
        """report_engine_api.md §8: int 1..99 -> float in [min,max]."""
        for key in ("volume", "dur_stretch", "pitch_stretch"):
            spec = params.PARAM_TABLE[key]
            for v in (1, 2, 50, 98, 99):
                f = params.encode_float(v, spec.float_min, spec.float_max)
                self.assertGreaterEqual(f, spec.float_min)
                self.assertLessEqual(f, spec.float_max)
            with self.assertRaises(params.ParamError):
                params.encode_float(0, spec.float_min, spec.float_max)
            with self.assertRaises(params.ParamError):
                params.encode_float(100, spec.float_min, spec.float_max)

    def test_float_encoding_range_endpoints(self):
        """report_engine_api.md §8: min/def/max float limits per key."""
        self.assertEqual(params.PARAM_TABLE["volume"].float_min, 0.0)
        self.assertEqual(params.PARAM_TABLE["volume"].float_def, 1.0)
        self.assertEqual(params.PARAM_TABLE["volume"].float_max, 1.6)
        self.assertEqual(params.PARAM_TABLE["dur_stretch"].float_min, 0.25)
        self.assertEqual(params.PARAM_TABLE["dur_stretch"].float_max, 1.5)
        self.assertEqual(params.PARAM_TABLE["pitch_stretch"].float_min, 0.9)
        self.assertEqual(params.PARAM_TABLE["pitch_stretch"].float_max, 1.1)

    def test_float_decode_bounds(self):
        spec = params.PARAM_TABLE["volume"]
        for v in (1, 50, 99):
            f = params.encode_float(v, spec.float_min, spec.float_max)
            out = params.decode_float(f, spec.float_min, spec.float_max)
            self.assertGreaterEqual(out, 1)
            self.assertLessEqual(out, 99)

    def test_string_defaults(self):
        """report_engine_api.md §8: default strings (text_encoding UTF-8)."""
        self.assertEqual(params.PARAM_TABLE["text_encoding"].string_default, "UTF-8")
        self.assertEqual(params.PARAM_TABLE["base_uri"].string_default, "")
        self.assertEqual(params.PARAM_TABLE["input_type"].string_default, "")

    def test_int_defaults(self):
        """report_engine_api.md §8: documented integer defaults."""
        self.assertEqual(params.PARAM_TABLE["sentence_break"].default, 400)
        self.assertEqual(params.PARAM_TABLE["paragraph_break"].default, 650)
        self.assertEqual(params.PARAM_TABLE["max_sentence_length"].default, 1000)
        self.assertEqual(params.PARAM_TABLE["max_word_length"].default, 100)

    def test_uri_scheme(self):
        """report_engine_api.md §8: base_uri must be file:// or http://."""
        self.assertTrue(params.uri_scheme_supported("file:///a"))
        self.assertTrue(params.uri_scheme_supported("http://x"))
        self.assertTrue(params.uri_scheme_supported(""))
        self.assertFalse(params.uri_scheme_supported("https://x"))

    def test_prop_names(self):
        """report_engine_api.md §8: KEY -> .vox property name."""
        self.assertEqual(params.PARAM_TABLE["volume"].prop, "amplify")
        self.assertEqual(params.PARAM_TABLE["dur_stretch"].prop, "duration_stretch")
        self.assertEqual(params.PARAM_TABLE["contrast"].prop, "eng_contrast")
        self.assertEqual(params.PARAM_TABLE["quality"].prop, "viterbi_beam")
        self.assertEqual(params.PARAM_TABLE["responsiveness"].prop, "tb_min_distance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
