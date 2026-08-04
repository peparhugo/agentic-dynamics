package codec

import (
	"crypto/rand"
	"encoding/binary"
	"sync/atomic"
)

const alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

var (
	base     = uint64(len(alphabet))
	decodeMap [256]byte
)

func init() {
	for i := range decodeMap {
		decodeMap[i] = 0xFF
	}
	for i := 0; i < len(alphabet); i++ {
		decodeMap[alphabet[i]] = byte(i)
	}
}

type Generator struct {
	counter atomic.Uint64
	machine uint64
}

func NewGenerator() *Generator {
	g := &Generator{}

	var buf [8]byte
	_, _ = rand.Read(buf[:])
	g.machine = binary.BigEndian.Uint64(buf[:])
	g.counter.Store(g.machine)

	return g
}

func (g *Generator) Encode(n uint64) string {
	if n == 0 {
		return string(alphabet[0])
	}

	var buf [11]byte
	i := len(buf)
	for n > 0 && i > 0 {
		i--
		buf[i] = alphabet[n%base]
		n /= base
	}
	return string(buf[i:])
}

func (g *Generator) Generate() string {
	n := g.counter.Add(1)
	return g.Encode(n)
}

func Decode(s string) (uint64, bool) {
	var n uint64
	for i := 0; i < len(s); i++ {
		v := decodeMap[s[i]]
		if v == 0xFF {
			return 0, false
		}
		n = n*base + uint64(v)
	}
	return n, true
}
