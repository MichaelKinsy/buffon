// SPDX-License-Identifier: MIT
// Vendored from PiG bench/k8s (MIT); see NOTICE.

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// object is a JSON object that keeps its key order, so pod lines and cluster-facts.json have a stable field order.
type object struct {
	keys   []string
	values map[string]json.RawMessage
}

func newObject() *object { return &object{values: map[string]json.RawMessage{}} }

// set replaces a key's value in place or appends the key.
func (o *object) set(key string, value any) {
	raw, err := marshalPlain(value)
	if err != nil {
		panic(fmt.Sprintf("buffon-cluster: encode %s: %v", key, err))
	}
	if _, ok := o.values[key]; !ok {
		o.keys = append(o.keys, key)
	}
	o.values[key] = raw
}

func (o *object) MarshalJSON() ([]byte, error) {
	var b bytes.Buffer
	b.WriteByte('{')
	for i, k := range o.keys {
		if i > 0 {
			b.WriteByte(',')
		}
		name, err := marshalPlain(k)
		if err != nil {
			return nil, err
		}
		b.Write(name)
		b.WriteByte(':')
		b.Write(o.values[k])
	}
	b.WriteByte('}')
	return b.Bytes(), nil
}

// marshalPlain encodes like JSON.stringify: no HTML escaping of <, > and &.
func marshalPlain(value any) ([]byte, error) {
	var b bytes.Buffer
	encoder := json.NewEncoder(&b)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(b.Bytes(), []byte("\n")), nil
}
