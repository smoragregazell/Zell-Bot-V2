
import os
from datetime import datetime
from zoneinfo import ZoneInfo

def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f'Error reading file {file_path}: {str(e)}'

def export_codebase():
    files_to_export = [
        'main.py',        
        'endpoints/classifier.py',
        'Tools/continuation_tool.py', 
        'Tools/iso_tool.py',
        'Tools/query_tool.py',
        'Tools/semantic_tool.py',
        'Tools/ticket_tool.py',
        'Tools/busquedacombinada_tool.py',
        'Tools/compararticket_tool.py',
        'Prompts/Clasificator/clasificadorprompt_v2.txt',
        'Prompts/Ticket/ticketprompt_v1.txt',
        'Prompts/Continuada/continuadaprompt_v1.txt',
        'Prompts/ISO/isoprompt_v1.txt',
        'Prompts/AnalisisQuery/analisisqueryprompt_v2.txt',
        'Prompts/Query/querypromt_v1.txt',
        'Prompts/BusquedaCombinada/busquedacombinadaprompt_v1.txt'
        'Prompts/CompararTicket/comparacionfinalprompt_v1.txt',
        'utils/logs.py',
        'utils/debug_logger.py',
        'utils/logging_config.py',
        'utils/contextManager/context_handler.py',
        'utils/contextManager/short_term_memory.py',
        'utils/llm_config.py',
        'utils/llm_provider.py',
        'utils/tool_registry.py',
        'utils/tool_response.py',
        'utils/prompt_loader.py',
        'test_api.py',
        'logadmin.py',
    ]
    
    os.makedirs('exports', exist_ok=True)
    timestamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y%m%d_%H%M%S")
    output_file = f'exports/codebase_export_{timestamp}.txt'
    
    with open(output_file, 'w', encoding='utf-8') as export:
        export.write('===== CODEBASE EXPORT =====\n')
        export.write(f'Date: {datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d %H:%M:%S")}\n')
        export.write(f'Total files: {len(files_to_export)}\n\n')
        
        for file_path in files_to_export:
            if os.path.exists(file_path):
                export.write('\n' + ('=' * 80) + '\n')
                export.write(f'FILE: {file_path}\n')
                export.write(('=' * 80) + '\n\n')
                content = read_file_content(file_path)
                export.write(content)
                export.write('\n\n')
            else:
                export.write('\n' + ('=' * 80) + '\n')
                export.write(f'FILE: {file_path} (NOT FOUND)\n')
                export.write(('=' * 80) + '\n\n')
    
    print(f'✅ Export completed! File saved to: {output_file}')

if __name__ == '__main__':
    export_codebase()
