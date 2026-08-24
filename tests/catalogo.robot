*** Settings ***
Library    Collections
Library    OperatingSystem
Library    String
Library    catalogo_api.CatalogoAPI


*** Variables ***
${OUTPUT_JSON}    resultado_catalogo.json
${OUTPUT_CSV}     produtos_por_estoque.csv


*** Test Cases ***
Processar Catalogo Completo Automaticamente
    [Documentation]    Busca catálogo completo, consulta estoques e organiza resultados.
    [Tags]    catalogo    api    estoque    completo

    Log    \n🚀 INICIANDO PROCESSAMENTO AUTOMÁTICO    console=True
    
    ${resultado} =    Processar Catalogo Completo
    
    ${success} =    Set Variable    ${resultado.get('success', False)}
    
    IF    not ${success}
        Log    ❌ Falha no processamento!    console=True
        Log    Erro: ${resultado.get('error', 'Desconhecido')}    console=True
        Fail    msg=Falha no processamento do catálogo
    END
    
    ${estoques_organizados} =    Set Variable    ${resultado['estoques_organizados']}
    ${produtos_com_estoque} =    Set Variable    ${resultado['produtos_com_estoque']}
    ${response_estoque} =    Set Variable    ${resultado['response_estoque']}
    
    ${total_produtos} =    Get Length    ${produtos_com_estoque}
    
    Log    \n✅ PROCESSAMENTO CONCLUÍDO!    console=True
    Log    Total de produtos com estoque: ${total_produtos}    console=True
    
    Log    \n===== CATÁLOGO ORGANIZADO POR ESTOQUE =====    console=True
    
    # Converte chaves para lista e itera
    ${estoque_ids} =    Evaluate    list($estoques_organizados.keys())
    
    FOR    ${estoque_id}    IN    @{estoque_ids}
        ${produtos_estoque} =    Evaluate    $estoques_organizados[str($estoque_id)]
        ${qtd_produtos} =    Get Length    ${produtos_estoque}
        
        Log    \n📦 Estoque ${estoque_id} (${qtd_produtos} produtos):    console=True
        ${'-' * 50}    Set Variable    value
        Log    ${'-' * 50}    console=True
        
        FOR    ${produto}    IN    @{produtos_estoque}
            ${produto_id} =    Set Variable    ${produto['id']}
            ${descricao} =    Set Variable    ${produto.get('descricao', 'N/A')}
            
            Log    ID: ${produto_id} | ${descricao}    console=True
        END
    END
    
    # Salvar JSON
    ${json_text} =    Evaluate
    ...    __import__('json').dumps($response_estoque, ensure_ascii=False, indent=2)
    
    Create File
    ...    ${OUTPUT_JSON}
    ...    ${json_text}
    ...    encoding=UTF-8
    
    # Salvar CSV
    ${csv_content} =    Set Variable    ESTOQUE;ID;DESCRICAO;CODIGO;UNIDADE\n
    
    FOR    ${estoque_id}    IN    @{estoque_ids}
        ${produtos_estoque} =    Evaluate    $estoques_organizados[$estoque_id]
        
        FOR    ${produto}    IN    @{produtos_estoque}
            ${pid} =    Set Variable    ${produto['id']}
            ${pdesc} =    Set Variable    ${produto.get('descricao', '')}
            ${pcod} =    Set Variable    ${produto.get('codigo', '')}
            ${puni} =    Set Variable    ${produto.get('unidade', '')}
            
            ${csv_content} =    Set Variable
            ...    ${csv_content}${estoque_id};${pid};${pdesc};${pcod};${puni}\n
        END
    END
    
    Create File
    ...    ${OUTPUT_CSV}
    ...    ${csv_content}
    ...    encoding=UTF-8
    
    Log    \n📁 Resultados salvos:    console=True
    Log    - JSON: ${OUTPUT_JSON}    console=True
    Log    - CSV: ${OUTPUT_CSV}    console=True