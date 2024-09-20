import numpy as np
import itertools
import random
import time

vertices = ["Growing (Bull)", "Decline (Bear)", "Stagnant (Recession)"]
combinations = list(itertools.product(vertices, repeat=2))

for comb in combinations:
    print(comb) 

edges = {
    ('Growing (Bull)', 'Growing (Bull)')            : 0.9,
    ('Growing (Bull)', 'Decline (Bear)')            : 0.075,
    ('Growing (Bull)', 'Stagnant (Recession)')      : 0.025,
    ('Decline (Bear)', 'Growing (Bull)')            : 0.15,
    ('Decline (Bear)', 'Decline (Bear)')            : 0.8,
    ('Decline (Bear)', 'Stagnant (Recession)')      : 0.05,
    ('Stagnant (Recession)', 'Growing (Bull)')      : 0.25,
    ('Stagnant (Recession)', 'Decline (Bear)')      : 0.25,
    ('Stagnant (Recession)', 'Stagnant (Recession)'): 0.5        
}

print(edges)

graph = (vertices, edges)

#Simple intuitive and very readable implementation based on dictionaries 
def evolve_the_economy(initial_state, graph, number_of_days):
    vertices, edges = graph
    count = {vertex: 0 for vertex in vertices}
    economy_history = {vertex: [] for vertex in vertices} #Keep track of the number of days in each state
    state = initial_state
    for day in range(number_of_days):
        transition_pronabilities = [ (edge[1], prob) for edge, prob in edges.items() if edge[0] == state ]
        elements, weights = zip(*transition_pronabilities)
        next_state = random.choices(elements, weights=weights, k=1)
        state = next_state[0]
        count[state] += 1
        for vertex in vertices:
            economy_history[vertex].append(count[vertex]/(day+1))  
    return economy_history



def test_randomness():
    initial_state = "Growing (Bull)"
    number_of_days = 100
    economy_history = evolve_the_economy(initial_state, graph, number_of_days)
    economy_history2 = evolve_the_economy(initial_state, graph, number_of_days)
    assert economy_history != economy_history2

def test_graph_well_defined():
    vertices, edges = graph
    #check that all the prob sum to 1 for each edge
    for vertex in vertices:
        sum_prob = sum([prob for edge, prob in edges.items() if edge[0] == vertex])
        assert sum_prob == 1
    #check that edges contain all possible transitions
    for vertex in vertices:
        for vertex2 in vertices:
            assert (vertex, vertex2) in edges.keys()

def test_number_of_days_in_history():
    initial_state = "Growing (Bull)"
    number_of_days = 100
    economy_history = evolve_the_economy(initial_state, graph, number_of_days)
    for vertex in vertices:
        assert len(economy_history[vertex]) == number_of_days

def test_regression_check_determinism():
    import pickle
    edges = {
        ('Growing (Bull)', 'Growing (Bull)')            : 0,
        ('Growing (Bull)', 'Decline (Bear)')            : 1,
        ('Growing (Bull)', 'Stagnant (Recession)')      : 0,
        ('Decline (Bear)', 'Growing (Bull)')            : 0,
        ('Decline (Bear)', 'Decline (Bear)')            : 0,
        ('Decline (Bear)', 'Stagnant (Recession)')      : 1,
        ('Stagnant (Recession)', 'Growing (Bull)')      : 1,
        ('Stagnant (Recession)', 'Decline (Bear)')      : 0,
        ('Stagnant (Recession)', 'Stagnant (Recession)'): 0        
    }
    initial_state = "Growing (Bull)"
    number_of_days = 100
    economy_history = evolve_the_economy(initial_state, (vertices, edges), number_of_days)
    #with open('economy_history_validated.pkl', 'wb') as file:
    #    pickle.dump(economy_history, file)
    with open('economy_history_validated.pkl', 'rb') as file:
        economy_history_validated = pickle.load(file)
    assert economy_history == economy_history_validated


