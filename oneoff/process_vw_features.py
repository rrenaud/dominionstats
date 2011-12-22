prefix = "Features^diff_"
values = []
for line in open('all_features_output.txt'):
    if line.startswith(prefix):
        line = line[len(prefix):]
        parts = line.strip().split(':')
        score = float(parts[3])
        card = parts[0]
        values.append((score, card))

values.sort()
values.reverse()
for score, card in values:
    print "%4.4f\t%s" % (score / 0.0372, card)

