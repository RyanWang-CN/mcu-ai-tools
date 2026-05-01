"""
Minimal ELF32 binary builder for testing pyelftools.
Generates a valid-but-tiny ELF file with .symtab section.
"""
import struct

def build_minimal_elf32(output_path, symbols=None):
    """
    Create a minimal valid ELF32 file with optional symbol entries.

    Args:
        output_path: str, path to write the ELF file
        symbols: list of (name, addr, size) tuples to include in .symtab
    """
    if symbols is None:
        symbols = [("test_var", 0x20000000, 4)]

    # ── ELF Header (Elf32_Ehdr = 52 bytes) ──
    e_ident = (
        b'\x7fELF'          # magic
        b'\x01'             # EI_CLASS: 32-bit
        b'\x01'             # EI_DATA: little-endian
        b'\x01'             # EI_VERSION: current
        b'\x00'             # EI_OSABI: System V
        b'\x00' * 8         # padding
    )
    e_type      = 2          # ET_EXEC
    e_machine   = 40         # EM_ARM
    e_version   = 1
    e_entry     = 0
    e_phoff     = 0          # no program headers
    e_shoff     = 52         # section headers start right after ELF header
    e_flags     = 0
    e_ehsize    = 52
    e_phentsize = 0
    e_phnum     = 0
    e_shentsize = 40         # Elf32_Shdr size
    e_shnum     = 3          # .shstrtab, .strtab, .symtab
    e_shstrndx  = 0          # first section is .shstrtab

    ehdr = struct.pack('<16sHHIIIIIHHHHHH',
        e_ident, e_type, e_machine, e_version, e_entry,
        e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize,
        e_phnum, e_shentsize, e_shnum, e_shstrndx)

    # ── Section data ──
    # Build section name string table (.shstrtab)
    sec_names = b'.shstrtab\x00.strtab\x00.symtab\x00'
    # Build symbol names string table (.strtab)
    sym_names = b'\x00'  # index 0 is empty
    name_offsets = []
    for name, addr, size in symbols:
        name_offsets.append(len(sym_names))
        sym_names += name.encode() + b'\x00'

    sym_entsize = 16  # Elf32_Sym
    num_syms = 1 + len(symbols)  # entry 0 + user symbols
    symtab_size = num_syms * sym_entsize

    # Layout: ehdr(52) | shdr(3*40=120) | .shstrtab | .strtab | .symtab
    shdr_offset = 52
    shstrtab_offset = shdr_offset + 3 * 40  # = 172
    strtab_offset = shstrtab_offset + len(sec_names)
    symtab_offset = strtab_offset + len(sym_names)

    # ── Section 0: .shstrtab ──
    def make_shdr(name_off, sh_type, sh_off, sh_size, link=0, info=0, align=1, entsize=0):
        return struct.pack('<IIIIIIIIII',
            name_off, sh_type, 0, 0, sh_off,
            sh_size, link, info, align, entsize)

    shdr0 = make_shdr(0, 3, shstrtab_offset, len(sec_names))  # SHT_STRTAB
    shdr1 = make_shdr(len(b'.shstrtab\x00'), 3, strtab_offset, len(sym_names))  # SHT_STRTAB
    shdr2 = make_shdr(
        len(b'.shstrtab\x00.strtab\x00'), 2, symtab_offset, symtab_size,
        link=1, align=4, entsize=sym_entsize
    )  # SHT_SYMTAB

    # ── Symbol entries (Elf32_Sym = 16 bytes each) ──
    # Entry 0: always empty
    sym_entries = [struct.pack('<IIIBBH', 0, 0, 0, 0, 0, 0)]
    for i, (name, addr, size) in enumerate(symbols):
        sym_entries.append(struct.pack('<IIIBBH',
            name_offsets[i], addr, size,
            0x10,  # STB_GLOBAL | STT_OBJECT
            0,     # other
            i + 1  # shndx (arbitrary but non-zero)
        ))
    symtab_data = b''.join(sym_entries)

    # ── Assemble ──
    with open(output_path, 'wb') as f:
        f.write(ehdr)
        f.write(shdr0 + shdr1 + shdr2)
        f.write(sec_names)
        f.write(sym_names)
        f.write(symtab_data)
