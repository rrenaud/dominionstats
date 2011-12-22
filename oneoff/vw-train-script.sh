vw -d ../data/test_huge_games.vw.txt -f ../data/huge_model.vw --loss_function logistic --adaptive --conjugate_gradient -c --passes 5
vw -t -d all_features_input.txt -i ../data/huge_model.vw --loss_function logistic -a | sed s/\\t/\\n/g > all_features_output.txt
