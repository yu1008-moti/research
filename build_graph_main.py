import scripts.construct_graph as cg
import matplotlib.pyplot as plt

if __name__ == "__main__":
    Sp_Mat_firm2firm, Sp_Mat_fin2firm, Tm_Mat_firm2firm, Tm_Mat_fin2fin = cg.construct_graph()
    target_firm_id = "13010"
    