// Read-only oracle: compile against the original Natal headers, not the PLC port.
#include <natal/single_box_movement.hpp>
#include <cstdlib>
#include <iostream>
int main(int argc, char** argv) {
  if (argc != 3) return 2;
  const unsigned effect = unsigned(std::strtoul(argv[1], nullptr, 10));
  const unsigned outputs = unsigned(std::strtoul(argv[2], nullptr, 10));
  const auto& sequence = natal::single_box_movement_sequence(effect, outputs);
  if (!sequence.valid || !sequence.units) return 3;
  std::cout << natal::single_box_movement_period(effect, outputs, 0) << ' '
            << sequence.count << ' ' << sequence.units << '\n';
  for (unsigned i = 0; i < sequence.count; ++i)
    std::cout << sequence.frames[i].mask << ' ' << unsigned(sequence.frames[i].units) << '\n';
  uint64_t elapsed;
  while (std::cin >> elapsed)
    std::cout << natal::single_box_movement_render(effect, outputs, elapsed, 0) << '\n';
}
