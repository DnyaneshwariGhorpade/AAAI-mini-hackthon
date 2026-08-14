from sklearn.metrics.pairwise import cosine_similarity

A=[[1,4,9],[1,2,3]]
B=[[7,2,3],[4,7,1]]
score=cosine_similarity(A,B)
print(score)