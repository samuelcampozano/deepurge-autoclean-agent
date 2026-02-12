module deepurge_anchor::deepurge_anchor {
    // ═══════════════════════════════════════════════════════════
    //  Deepurge Anchor – On-Chain Report Root Hash Registry
    //
    //  Stores a mapping of  date → SHA-256 root hash  so anyone
    //  can verify that daily file-management reports produced by
    //  the Deepurge AutoClean Agent haven't been tampered with.
    //
    //  Author: Samuel Campozano Lopez
    //  Project: Sui Hackathon 2026
    // ═══════════════════════════════════════════════════════════

    use sui::event;
    use sui::table::{Self, Table};

    // ─── Error Codes ──────────────────────────────────────
    const E_NOT_OWNER: u64 = 0;
    const E_DATE_EXISTS: u64 = 1;

    // ─── Structs ──────────────────────────────────────────

    /// Shared object holding every anchored root hash.
    public struct Registry has key {
        id: UID,
        owner: address,
        entries: Table<vector<u8>, vector<u8>>,   // date_bytes → hash_bytes
        anchor_count: u64,
    }

    /// Emitted whenever a new root hash is anchored.
    public struct AnchorEvent has copy, drop {
        date: vector<u8>,
        root_hash: vector<u8>,
        anchor_count: u64,
    }

    // ─── Init ─────────────────────────────────────────────

    /// Called once at publish time.  Creates the shared Registry.
    fun init(ctx: &mut TxContext) {
        let registry = Registry {
            id: object::new(ctx),
            owner: tx_context::sender(ctx),
            entries: table::new<vector<u8>, vector<u8>>(ctx),
            anchor_count: 0,
        };
        transfer::share_object(registry);
    }

    // ─── Public Entry Functions ───────────────────────────

    /// Anchor a daily-report root hash.
    /// Only the registry owner may call this.
    public entry fun anchor_report(
        registry: &mut Registry,
        date: vector<u8>,
        root_hash: vector<u8>,
        ctx: &mut TxContext,
    ) {
        assert!(tx_context::sender(ctx) == registry.owner, E_NOT_OWNER);
        assert!(!table::contains(&registry.entries, date), E_DATE_EXISTS);

        table::add(&mut registry.entries, date, root_hash);
        registry.anchor_count = registry.anchor_count + 1;

        event::emit(AnchorEvent {
            date,
            root_hash,
            anchor_count: registry.anchor_count,
        });
    }

    // ─── View Functions ───────────────────────────────────

    /// Check whether a date has been anchored.
    public fun has_anchor(registry: &Registry, date: vector<u8>): bool {
        table::contains(&registry.entries, date)
    }

    /// Retrieve the stored root hash for a given date.
    public fun get_hash(registry: &Registry, date: vector<u8>): &vector<u8> {
        table::borrow(&registry.entries, date)
    }

    /// How many reports have been anchored in total.
    public fun anchor_count(registry: &Registry): u64 {
        registry.anchor_count
    }
}
