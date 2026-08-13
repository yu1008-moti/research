import scripts.construct_edge as ce
import scripts.construct_node as cn

import sys

if __name__ == "__main__":
    target = sys.argv[1]
    if target == "edge":
        ce.register_edges()
    elif target == "node":
        cn.register_nodes()