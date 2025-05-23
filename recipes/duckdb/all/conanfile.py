from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import apply_conandata_patches, export_conandata_patches, get, copy, rm, rmdir, replace_in_file
from conan.tools.build import check_min_cppstd, cross_building
from conan.tools.scm import Version
from conan.tools.microsoft import is_msvc
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout

import glob
import os

required_conan_version = ">=2.1"

class DuckdbConan(ConanFile):
    name = "duckdb"
    description = "DuckDB is an embeddable SQL OLAP Database Management System"
    license = "MIT"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/cwida/duckdb"
    topics = ("sql", "database", "olap", "embedded-database")
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_autocomplete": [True, False],
        "with_icu": [True, False],
        "with_tpch": [True, False],
        "with_tpcds": [True, False],
        "with_fts": [True, False],
        "with_visualizer": [True, False],
        "with_httpfs": [True, False],
        "with_json": [True, False],
        "with_excel": [True, False],
        "with_inet": [True, False],
        "with_sqlsmith": [True, False],
        "with_odbc": [True, False],
        "with_query_log": [True, False],
        "with_shell": [True, False],
        "with_threads": [True, False],
        "with_rdtsc": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_autocomplete": False,
        "with_icu": False,
        "with_tpch": False,
        "with_tpcds": False,
        "with_fts": False,
        "with_visualizer": False,
        "with_httpfs": False,
        "with_json": False,
        "with_excel": False,
        "with_inet": False,
        "with_sqlsmith": False,
        "with_odbc": False,
        "with_query_log": False,
        "with_shell": False,
        "with_threads": True,
        "with_rdtsc": False,
    }
    short_paths = True

    @property
    def _min_cppstd(self):
        return 11

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        if Version(self.version) >= "1.1.0":
            del self.options.with_odbc

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        # FIXME: duckdb vendors a bunch of deps by modify the source code to have their own namespace
        if self.options.get_safe("with_odbc"):
            self.requires("odbc/2.3.11")
        if self.options.with_httpfs:
            self.requires("openssl/[>=1.1 <4]")

    def validate(self):
        if self.settings.compiler.cppstd:
            check_min_cppstd(self, self._min_cppstd)
        # FIXME: drop support MSVC debug shared build
        if Version(self.version) >= "0.9.2" and \
                is_msvc(self) and self.options.shared and self.settings.build_type == "Debug":
            raise ConanInvalidConfiguration(f"{self.ref} does not support MSVC debug shared build")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], destination=self.source_folder, strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["DUCKDB_MAJOR_VERSION"] = Version(self.version).major
        tc.variables["DUCKDB_MINOR_VERSION"] = Version(self.version).minor
        tc.variables["DUCKDB_PATCH_VERSION"] = Version(self.version).patch
        tc.variables["DUCKDB_DEV_ITERATION"] = 0
        tc.variables["OVERRIDE_GIT_DESCRIBE"] = f"v{self.version}"

        build_extensions = ""
        if self.options.with_icu:
            build_extensions += ";icu"
        if self.options.with_autocomplete:
            build_extensions += ";autocomplete"
        if self.options.with_tpch:
            build_extensions += ";tpch"
        if self.options.with_tpcds:
            build_extensions += ";tpcds"
        if self.options.with_fts:
            build_extensions += ";fts"
        if self.options.with_visualizer:
            build_extensions += ";visualizer"
        if self.options.with_httpfs:
            build_extensions += ";httpfs"
        if self.options.with_json:
            build_extensions += ";json"
        if self.options.with_excel:
            build_extensions += ";excel"
        if self.options.with_inet:
            build_extensions += ";inet"
        if self.options.with_sqlsmith:
            build_extensions += ";sqlsmith"
        tc.variables["BUILD_EXTENSIONS"] = build_extensions

        if "with_odbc" in self.options:
            tc.variables["BUILD_ODBC_DRIVER"] = self.options.with_odbc
        tc.variables["FORCE_QUERY_LOG"] = self.options.with_query_log
        tc.variables["BUILD_SHELL"] = self.options.with_shell
        tc.variables["DISABLE_THREADS"] = not self.options.with_threads
        tc.variables["BUILD_UNITTESTS"] = False
        tc.variables["BUILD_RDTSC"] = self.options.with_rdtsc
        tc.variables["EXTENSION_STATIC_BUILD"] = not self.options.shared
        tc.variables["ENABLE_SANITIZER"] = False
        tc.variables["ENABLE_UBSAN"] = False
        if is_msvc(self) and not self.options.shared:
            tc.preprocessor_definitions["DUCKDB_API"] = ""
        if Version(self.version) >= "0.10.0" and cross_building(self):
            tc.variables["DUCKDB_EXPLICIT_PLATFORM"] = f"{self.settings.os}_{self.settings.arch}"
        tc.generate()

        dpes = CMakeDeps(self)
        dpes.generate()

    def build(self):
        apply_conandata_patches(self)
        if is_msvc(self) and not self.options.shared:
            replace_in_file(self, os.path.join(self.source_folder, "src", "include", "duckdb.h"),
                            "#define DUCKDB_API __declspec(dllimport)",
                            "#define DUCKDB_API"
                            )
            replace_in_file(self, os.path.join(self.source_folder, "src", "include", "duckdb", "common", "winapi.hpp"),
                            "#define DUCKDB_API __declspec(dllimport)",
                            "#define DUCKDB_API"
                            )

        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, pattern="LICENSE", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)
        cmake = CMake(self)
        cmake.install()

        if self.options.shared:
            rm(self, "duckdb_*.lib", os.path.join(self.package_folder, "lib"))
            for lib in glob.glob(os.path.join(self.package_folder, "lib", "*.a")):
                if not lib.endswith(".dll.a"):
                    os.remove(lib)

        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rmdir(self, os.path.join(self.package_folder, "cmake"))

    def package_info(self):
        if self.options.shared:
            self.cpp_info.libs = ["duckdb"]
        else:
            self.cpp_info.libs = [
                "duckdb_static",
                "duckdb_fmt",
                "duckdb_pg_query",
                "duckdb_re2",
                "duckdb_miniz",
                "duckdb_utf8proc",
                "duckdb_hyperloglog",
                "duckdb_fastpforlib",
                "duckdb_mbedtls",
            ]
            self.cpp_info.libs.append("duckdb_fsst")
            if Version(self.version) >= "0.10.0":
                self.cpp_info.libs.append("duckdb_skiplistlib")
            if Version(self.version) >= "0.10.3":
                self.cpp_info.libs.append("duckdb_yyjson")

            if self.options.with_autocomplete:
                self.cpp_info.libs.append("autocomplete_extension")
            if self.options.with_icu:
                self.cpp_info.libs.append("icu_extension")
            if self.options.get_safe("with_parquet", True):
                self.cpp_info.libs.append("parquet_extension")
            if self.options.with_tpch:
                self.cpp_info.libs.append("tpch_extension")
            if self.options.with_tpcds:
                self.cpp_info.libs.append("tpcds_extension")
            if self.options.with_fts:
                self.cpp_info.libs.append("fts_extension")
            if self.options.with_visualizer:
                self.cpp_info.libs.append("visualizer_extension")
            if self.options.with_httpfs:
                self.cpp_info.libs.append("httpfs_extension")
            if (self.settings.os == "Linux" and
                (Version(self.version) < "0.10.1" or self.settings.arch == "x86_64")):
                self.cpp_info.libs.append("jemalloc_extension")
            if self.options.with_json:
                self.cpp_info.libs.append("json_extension")
            if self.options.with_excel:
                self.cpp_info.libs.append("excel_extension")
            if self.options.with_inet:
                self.cpp_info.libs.append("inet_extension")
            if self.options.with_sqlsmith:
                self.cpp_info.libs.append("sqlsmith_extension")

        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs.extend(["pthread", "dl", "m"])

        if self.settings.os == "Windows":
            self.cpp_info.system_libs.append("ws2_32")
            if Version(self.version) >= "0.10.0":
                self.cpp_info.system_libs.extend(["rstrtmgr", "bcrypt"])
