from string import Template

class rel_sql:
    ## DATABASE PATHS
    PATH_ORIGINAL_DB = "./db/synthesis/synthesis.duckdb"
    PATH_GRAPHINFO_DB = Template("./scripts/datap/graph_v2/DS/graph_info_${serial_id}.duckdb")

    ## SQL FILE PATHS
    PATH_SQL_TO_FETCH_PRICES = "./scripts/datap/graph_v2/sql/get_table_to_CAPM.sql"
    PATH_SQL_TO_FETCH_FINANCIALS = "./scripts/datap/graph_v2/sql/get_fin_data_by_week.sql"

    PATH_SQL_TO_INSERT_TO_FEATS_TABLE = "./scripts/datap/graph_v2/sql/insert_to_feats_table.sql"
    PATH_SQL_TO_INSERT_TO_NODE_TABLE = "./scripts/datap/graph_v2/sql/insert_to_node_table.sql"
    PATH_SQL_TO_INSERT_TO_EDGE_TABLE = "./scripts/datap/graph_v2/sql/insert_to_edge_table.sql"

    PATH_SQL_TO_CREATE_GRAPHINFO_TABLE = "./scripts/datap/graph_v2/sql/create_graph_info_table.sql"

    # SQL PARAMETERS
    START_WEEK_ID = 200819
    END_WEEK_ID = 202616