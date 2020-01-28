// Copyright 2017 syzkaller project authors. All rights reserved.
// Use of this source code is governed by Apache 2 LICENSE that can be found in the LICENSE file.

package main

import (
	"github.com/google/syzkaller/pkg/cover"
	"sync"
	"time"

	"github.com/google/syzkaller/pkg/log"
)

type ProgQueue struct {
	mu               sync.RWMutex
	programin        []*ProgramIn
	programout       []*ProgramOut
	programwait      map[string]*ProgramWait
}

type ProgramIn struct{
	Trace []int
	Name string
	Retry int
}

type ProgramWait struct{
	Trace []int
	Name string
	Retry int
	Timer *time.Timer
}

type ProgramOut struct{
	Trace []int
	Coverage []cover.Cover
	Name string
}

const(
	wantIn int = 0
	wantOut int = 1
)

func newProgQueue() *ProgQueue {
	return &ProgQueue{
		programwait:  make(map[string]*ProgramWait),
	}
}

func (pq *ProgQueue) enqueue(item interface{}) {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	switch item := item.(type) {
	case *ProgramIn:
		pq.programin = append(pq.programin, item)
	case *ProgramOut:
		pq.programout = append(pq.programout, item)
		waitItem, ok := pq.programwait[item.Name]
		if ok {
			waitItem.Timer.Stop()
			delete(pq.programwait, item.Name)
		}
	default:
		panic("unknown work type")
	}
}

func (pq *ProgQueue) dequeue(types int) (item interface{}) {
	pq.mu.Lock()
	defer pq.mu.Unlock()
	switch types {
	case wantIn:
		{
			if len(pq.programin) != 0 {
				item = pq.programin[0]
				pq.programin = pq.programin[1:len(pq.programin)]

				program := item.(*ProgramIn)
				if program.Retry >= 5 {
					return item
				}
				waitItem := &ProgramWait{
					Trace: program.Trace,
					Name:  program.Name,
					Retry: program.Retry,
					Timer:  time.NewTimer(10 * time.Second),
				}
				pq.programwait[program.Name] = waitItem
				go func() {
					<-waitItem.Timer.C
					pq.mu.Lock()
					pq.programin = append(pq.programin, &ProgramIn{
						Trace: waitItem.Trace,
						Name:  waitItem.Name,
						Retry: waitItem.Retry+1,
					})
					delete(pq.programwait, waitItem.Name)
					pq.mu.Unlock()
				}()
			} else {
				return nil
			}
		}
	case wantOut:
		{
			if len(pq.programout) != 0 {
				item = pq.programout[0]
				pq.programout = pq.programout[1:len(pq.programout)]
			} else {
				return nil
			}
		}
	default:
		panic("unknown work type")
	}
	return item
}

func (pq *ProgQueue) print() {
	pq.mu.RLock()
	defer pq.mu.RUnlock()
	log.Logf(0, "Length of ProgramIn is %v\n", len(pq.programin))
	log.Logf(0, "Length of ProgramWait is %v\n", len(pq.programwait))
	log.Logf(0, "Length of ProgramOut is %v\n", len(pq.programout))
}