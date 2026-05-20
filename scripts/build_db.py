from scripts.data_processing.construct_db import *

def build_homogenous_db():

    constructer = HomogenousConstructor(
        nparray_dir=Path("masks"), 
        financial_data_dir=Path("data_financial")
    )

    constructer.start_build(db_name="homogenous_data.db")

def build_heterogenous_db():
    pass