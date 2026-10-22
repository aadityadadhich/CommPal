from backend.r5_platform_orchestrator.seed import init_db, seed_week_with_asha, SessionLocal

__all__ = ["init_db", "seed_week_with_asha"]

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    seed_week_with_asha(db)
    db.close()
    print("Database seeded with 'Week with Asha' scenario successfully.")
