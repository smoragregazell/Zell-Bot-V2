
import os
from datetime import datetime
from zoneinfo import ZoneInfo

def read_file_content(file_path):
    """Read the content of a file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

def export_codebase():
    """Export important project files to a single text document."""
    # Define the files to export based on current structure
    files_to_export = [
        # Core files
        "main.py",
        # Endpoints
        "endpoints/classifier.py",
        # Tools
        "Tools/continuation_tool.py",
        "Tools/iso_tool.py",
        "Tools/query_tool.py",
        "Tools/search_tickets.py",
        "Tools/semantic_followup_tool.py",
        # Prompts
        "Prompts/Clasificador/clasificadorprompt_v1.txt",
        "Prompts/Ticket/ticketprompt_v1.txt",
        "Prompts/Continuada/continuadaprompt_v1.txt",
        "Prompts/conversationsummary_prompt_v1.txt",
        "Prompts/ISO/isoprompt_v1.txt",
        "Prompts/AnalisisQuery/analisisqueryprompt_v1.txt",
        "Prompts/Query/queryprompt_v1.txt",
        # Utilities
        "utils/logs.py",
        "utils/contextManager/context_handler.py",
        "utils/contextManager/short_term_memory.py"
    ]
    
    # Create exports directory if it doesn't exist
    os.makedirs("exports", exist_ok=True)
    
    # Generate timestamp for the filename
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y%m%d_%H%M%S")
    output_file = f"exports/codebase_export_{timestamp}.txt"
    
    # Create the export file
    with open(output_file, 'w', encoding='utf-8') as export:
        # Write header with project info
        export.write(f"===== CODEBASE EXPORT =====\n")
        export.write(f"Date: {datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y%m%d_%H%M%S")}\n")
        export.write(f"Total files: {len(files_to_export)}\n\n")
        
        # Process each file
        for file_path in files_to_export:
            if os.path.exists(file_path):
                # Write file header
                export.write(f"\n{'=' * 80}\n")
                export.write(f"FILE: {file_path}\n")
                export.write(f"{'=' * 80}\n\n")
                
                # Write file content
                content = read_file_content(file_path)
                export.write(content)
                export.write("\n\n")
            else:
                export.write(f"\n{'=' * 80}\n")
                export.write(f"FILE: {file_path} (NOT FOUND)\n")
                export.write(f"{'=' * 80}\n\n")
    
    return output_file

if __name__ == "__main__":
    try:
        export_path = export_codebase()
        print(f"✅ Export completed! File saved to: {export_path}")
    except Exception as e:
        print(f"❌ Error during export: {str(e)}")
