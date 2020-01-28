// Copyright 2015 syzkaller project authors. All rights reserved.
// Use of this source code is governed by Apache 2 LICENSE that can be found in the LICENSE file.

package prog

import (
	"math/rand"
)

// Generate generates a random program of length ~ncalls.
// calls is a set of allowed syscalls, if nil all syscalls are used.
func (target *Target) Generate(rs rand.Source, ncalls int, ct *ChoiceTable) *Prog {
	p := &Prog{
		Target: target,
	}
	r := newRand(target, rs)
	s := newState(target, ct, nil)
	for len(p.Calls) < ncalls {
		calls := r.generateCall(s, p, len(p.Calls))
		for _, c := range calls {
			s.analyze(c)
			p.Calls = append(p.Calls, c)
		}
	}
	p.debugValidate()
	return p
}

func (target *Target) Generate_Fixed(sequence []int, rs rand.Source, ncalls int, ct *ChoiceTable) (*Prog, []int) {
	p := &Prog{
		Target: target,
	}
	var trace []int
	r := newRand(target, rs)
	s := newState(target, ct, nil)

	for _, id := range sequence {
		calls := r.generateSeqCall(s, id)
		if len(calls) > 1{
			trace = append(trace, -1)
			continue
		}
		s.analyze(calls[0])
		trace = append(trace, id)
		p.Calls = append(p.Calls, calls[0])
	}
	p.debugValidate()
	return p, trace
}


func (target *Target) Generate_ForFuzz(sequence []int, rs rand.Source, ncalls int, ct *ChoiceTable) *Prog {
	p := &Prog{
		Target: target,
	}
	r := newRand(target, rs)
	s := newState(target, ct, nil)

	for _, id := range sequence {
		calls := r.generateSeqCall(s, id)
		for _, c := range calls {
			s.analyze(c)
			p.Calls = append(p.Calls, c)
		}
	}
	p.debugValidate()
	return p
}


