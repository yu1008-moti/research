from scripts.data_processing.construct_db import *

def build_homogenous_db():

    constructer = HomogenousDBConstructor(
        nparray_dir=Path("masks"), 
        financial_data_dir=Path("data_financial")
    )

    constructer.start_build(db_name="homogenous_data.db", table_name="homogenous_table")

def build_homogenous_features_parquet():
    pass

def build_heterogenous_db():
    pass