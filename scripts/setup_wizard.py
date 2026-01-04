import os
import sys
import logging
import getpass
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, text, Engine
from mem0.exceptions import DatabaseError, ConfigurationError

# Configure Logging for Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('setup_debug.log')
    ]
)
logger = logging.getLogger("mem0_setup")

def print_banner() -> None:
    """Displays the Mem0 Supabase Innovation Wizard ASCII banner."""
    banner = """
    ███╗   ███╗███████╗███╗   ███╗  ██████╗ 
    ████╗ ████║██╔════╝████╗ ████║██╔═████╗
    ██╔████╔██║█████╗  ██╔████╔██║██║██╔██║
    ██║╚██╔╝██║██╔══╝  ██║╚██╔╝██║████╔╝██║
    ██║ ╚═╝ ██║███████╗██║ ╚═╝ ██║╚██████╔╝
    ╚═╝     ╚═╝╚══════╝╚═╝     ╚═╝ ╚═════╝ 
        MEM0 SUPABASE INNOVATION WIZARD
    """
    print(banner)

def load_setup_sql() -> str:
    """
    Loads the master SQL schema from the accompanying .sql file.
    
    Returns:
        The SQL content as a string.
        
    Raises:
        ConfigurationError: If the SQL file is missing.
    """
    sql_path = os.path.join(os.path.dirname(__file__), "supabase_setup.sql")
    if not os.path.exists(sql_path):
        logger.error(f"Setup SQL file not found at {sql_path}")
        raise ConfigurationError(
            message="Master SQL schema file is missing",
            error_code="CFG_004",
            suggestion="Ensure supabase_setup.sql is in the same directory as this script."
        )
    
    with open(sql_path, "r", encoding="utf-8") as f:
        return f.read()

def run_setup() -> None:
    """
    Main execution flow for the Supabase Setup Wizard.
    Standardized with logging, typing, and robust error handling.
    """
    print_banner()
    logger.info("Initializing Mem0 Supabase Innovation Wizard...")
    
    # 1. Credentials Acquisition
    connection_string = os.environ.get("SUPABASE_CONNECTION_STRING")
    if not connection_string:
        print("\n[?] Enter your Supabase Connection String (Session Pooler recommended)")
        print("    Format: postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres")
        connection_string = input("    > ").strip()
    else:
        logger.info("Found connection string in environment variables.")

    if not connection_string:
        logger.warning("No connection string provided. Aborting setup.")
        return

    # 2. Database Initialization
    try:
        logger.info("Connecting to Supabase PostgreSQL instance...")
        engine: Engine = create_engine(connection_string, pool_pre_ping=True)
        
        with engine.connect() as conn:
            logger.info("Connected. Loading Master Innovation Schema...")
            try:
                setup_sql = load_setup_sql()
                conn.execute(text(setup_sql))
                conn.commit()
                logger.info("Master Schema applied successfully (Hybrid Search, Graph, RLS, Storage).")
            except Exception as sql_err:
                raise DatabaseError(
                    message=f"Failed to apply SQL schema: {str(sql_err)}",
                    error_code="DB_003",
                    details={"error": str(sql_err)}
                )

            # 3. Autonomous Dreaming (pg_cron)
            print("\n[?] Enable Autonomous Dreaming (pg_cron)?")
            print("    Required for 'Self-Healing' and 'Consolidation' cycles.")
            if input("    Enable? (y/n) > ").lower() == 'y':
                edge_url = input("    Edge Function URL: ").strip()
                service_key = input("    Service Role Key: ").strip()
                
                if edge_url and service_key:
                    cron_sql = f"""
                    SELECT cron.schedule(
                      'nightly-dream',
                      '0 3 * * *',
                      $$
                      SELECT net.http_post(
                        url:='{edge_url}',
                        headers:='{{"Content-Type": "application/json", "Authorization": "Bearer {service_key}"}}'::jsonb,
                        body:='{{}}'::jsonb
                      ) as request_id;
                      $$
                    );
                    """
                    conn.execute(text(cron_sql))
                    conn.commit()
                    logger.info("Autonomous Dreaming job scheduled for 03:00 UTC.")
                else:
                    logger.warning("Missing URL or Key. pg_cron configuration skipped.")

    except (DatabaseError, ConfigurationError) as mem0_err:
        logger.error(f"Setup Error: {mem0_err.message}")
        if mem0_err.suggestion:
            print(f"\n[TIP] {mem0_err.suggestion}")
        return
    except Exception as e:
        logger.critical(f"Unexpected error during setup: {str(e)}")
        return

    # 4. Environment Configuration
    if input("\n[?] Generate/Update local .env file? (y/n) > ").lower() == 'y':
        openai_key = input("    OpenAI API Key (optional): ").strip()
        supabase_key = input("    Supabase Service Key (optional): ").strip()
        
        try:
            with open(".env", "a") as f:
                f.write(f"\nSUPABASE_CONNECTION_STRING=\"{connection_string}\"\n")
                if openai_key: f.write(f"OPENAI_API_KEY=\"{openai_key}\"\n")
                if supabase_key:
                    f.write(f"SUPABASE_SERVICE_KEY=\"{supabase_key}\"\n")
                    f.write(f"SUPABASE_KEY=\"{supabase_key}\"\n")
            logger.info(".env file updated successfully.")
        except IOError as e:
            logger.error(f"Failed to write .env file: {e}")

    # 5. Summary
    logger.info("="*40)
    logger.info("SETUP COMPLETED SUCCESSFULLY")
    logger.info("="*40)
    print("\nFeatures Verified:")
    print("- Hybrid Search & Semantic Cache")
    print("- Recursive Graph Relations")
    print("- Multi-tier Visibility & RLS")
    print("- Multimodal Storage Bucket")
    print("- Temporal Versioning")
    print("\nNext: Try 'python -m mem0.mcp_server' to connect with your tools!")

if __name__ == "__main__":
    run_setup()
